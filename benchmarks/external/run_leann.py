"""LEANN compact HNSW vs exact FAISS with identical MiniLM embeddings.

Use an isolated Python environment with leann==0.3.8 and psutil. Model downloads
are preparatory and excluded from timed indexing; their storage is reported.
"""

import os
import json
import time
import pathlib
import argparse
import threading
import logging


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=pathlib.Path, required=True)
    ap.add_argument("--output", type=pathlib.Path, default=pathlib.Path(__file__).parent)
    a = ap.parse_args()
    base = a.work
    base.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(base / "huggingface")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from fixture import make
    from leann import LeannBuilder, LeannSearcher
    from sentence_transformers import SentenceTransformer
    import faiss
    import psutil

    logging.getLogger("leann.api").setLevel(logging.WARNING)
    corpus = base / "corpus-leann"
    queries = make(corpus)
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    # Explicitly prepare the free local model before the timed build.
    t = time.perf_counter()
    model = SentenceTransformer(model_name)
    model_prepare = time.perf_counter() - t
    files = sorted(p for p in corpus.iterdir() if p.suffix in [".md", ".py"])
    texts = [p.read_text() for p in files]

    def disk(root):
        return sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink())

    samples = []
    stop = threading.Event()
    proc = psutil.Process()

    def sample():
        while not stop.wait(0.02):
            try:
                samples.append(
                    sum(x.memory_info().rss for x in [proc] + proc.children(recursive=True) if x.is_running())
                )
            except psutil.Error:
                pass

    threading.Thread(target=sample, daemon=True).start()

    for name in ["faiss", "leann"]:
        folder = base / ("measured-" + name)
        if folder.exists():
            raise SystemExit(f"Refusing to replace {folder}; use fresh directory or archive it")
        folder.mkdir()
        t = time.perf_counter()
        if name == "faiss":
            vectors = model.encode(texts, normalize_embeddings=True).astype("float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(folder / "index.faiss"))
            (folder / "passages.json").write_text(
                json.dumps([{"file": p.name, "text": p.read_text()} for p in files])
            )
        else:
            path = str(folder / "corpus.leann")
            builder = LeannBuilder(
                backend_name="hnsw",
                embedding_model=model_name,
                embedding_mode="sentence-transformers",
                is_compact=True,
            )
            for p in files:
                builder.add_text(p.read_text(), metadata={"file": p.name})
            builder.build_index(path)
            searcher = LeannSearcher(path, use_daemon=False)
        indexed = time.perf_counter() - t
        results = []

        def search(q):
            if name == "faiss":
                v = model.encode([q], normalize_embeddings=True).astype("float32")
                scores, ids = index.search(v, 5)
                return [files[i].name for i in ids[0]], scores[0].tolist()
            found = searcher.search(q, top_k=5, complexity=32)
            return [r.metadata["file"] for r in found], [float(r.score) for r in found]

        t = time.perf_counter()
        search(queries[0]["query"])
        first_query = (time.perf_counter() - t) * 1000
        samples.clear()
        for row in queries:
            t = time.perf_counter()
            found, scores = search(row["query"])
            elapsed = (time.perf_counter() - t) * 1000
            results.append({**row, "latency_ms": elapsed, "files": found, "scores": scores})
        report = {
            "tool": name,
            "version": "leann 0.3.8 / faiss 1.15.1",
            "model": model_name,
            "mode": "hnsw compact, complexity 32, top 5"
            if name == "leann"
            else "IndexFlatIP normalized float32 exact, top 5",
            "index_seconds": indexed,
            "index_bytes": disk(folder),
            "model_bytes": disk(base / "huggingface" / "hub"),
            "model_prepare_seconds": model_prepare,
            "first_query_ms": first_query,
            "query_timing": "warm in-process API after one warm-up; not comparable to CLI startup measurements",
            "peak_query_tree_rss_bytes": max(samples, default=None),
            "query_tree_sampling_ms": 20,
            "queries": results,
        }
        (a.output / (name + ".json")).write_text(json.dumps(report, indent=2))
        print(name, "done", flush=True)
    stop.set()


if __name__ == "__main__":
    main()
