"""Matched MiniLM RAVEL API plus default lexical CLI on the independent fixture."""

from pathlib import Path
import argparse
import json
import time
import os
import resource
from fixture import make
from run_cli import run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path(__file__).parent)
    a = ap.parse_args()
    os.environ["HF_HOME"] = str(a.work / "huggingface")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from ravel import Index
    from ravel.embeddings import pack
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)

    class MiniLM:
        def embed(self, texts, *, query=False):
            # No model-specific BGE query prefix: same MiniLM query inputs as FAISS/LEANN; native document chunks differ.
            return [
                pack(v) for v in model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
            ]

    root = a.work / "measured-ravel-api"
    if root.exists():
        raise SystemExit("Refusing to replace " + str(root))
    queries = make(root)
    t = time.perf_counter()
    index = Index(root, embedder=MiniLM())
    index.sync()
    lexical_seconds = time.perf_counter() - t
    t = time.perf_counter()
    index.materialize()
    materialize_seconds = time.perf_counter() - t
    for mode in ["semantic", "auto"]:
        t = time.perf_counter()
        index.search(queries[0]["query"], mode=mode, token_budget=8192, limit=5, latency_ms=60000)
        first = (time.perf_counter() - t) * 1000
        rows = []
        for row in queries:
            t = time.perf_counter()
            r = index.search(row["query"], mode=mode, token_budget=8192, limit=5, latency_ms=60000)
            elapsed = (time.perf_counter() - t) * 1000
            rows.append(
                {
                    **row,
                    "latency_ms": elapsed,
                    "files": [r["path"] for r in r["results"]],
                    "strategy": r["plan"]["strategy"],
                    "context_upper_bound": r["metrics"]["tokens_used"],
                    "semantic_coverage": r["metrics"]["semantic_coverage"],
                }
            )
        report = {
            "tool": "ravel",
            "mode": mode,
            "model": model_name,
            "model_note": "Injected model-matched MiniLM instead of product-default BGE. Int8 stored vectors.",
            "index_seconds": lexical_seconds,
            "materialize_seconds": materialize_seconds,
            "index_bytes": index.path.stat().st_size,
            "query_timing": "warm in-process API after one warm-up, full source freshness scan included",
            "first_query_ms": first,
            "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "queries": rows,
        }
        (a.output / ("ravel-matched-" + mode + ".json")).write_text(json.dumps(report, indent=2))
        print("ravel", mode, "done", flush=True)
    index.close()
    # No model support enabled in this separately indexed default lexical CLI.
    root = a.work / "measured-ravel-cli"
    if root.exists():
        raise SystemExit("Refusing to replace " + str(root))
    queries = make(root)
    cmd = [str(Path(__import__("sys").executable)), "-m", "ravel"]
    env = os.environ.copy()
    indexed = run(cmd + ["index", str(root), "--json"], root, env)
    indexed.pop("stdout", None)
    indexed.pop("stderr", None)
    rows = []
    for row in queries:
        r = run(
            cmd + ["search", row["query"], "--root", str(root), "--json", "--tokens", "8192", "--limit", "5"],
            root,
            env,
        )
        raw = json.loads(r.pop("stdout"))
        r.pop("stderr", None)
        rows.append({**row, **r, "files": [x["path"] for x in raw["results"]]})
    (a.output / "ravel-lexical-cli.json").write_text(
        json.dumps(
            {
                "tool": "ravel",
                "mode": "lexical CLI default no model",
                "index": indexed,
                "index_bytes": (root / ".ravel/index.sqlite3").stat().st_size,
                "query_timing": "fresh CLI process per query, warm OS cache, full source freshness scan included",
                "queries": rows,
            },
            indent=2,
        )
    )
    print("ravel lexical CLI done", flush=True)


if __name__ == "__main__":
    main()
