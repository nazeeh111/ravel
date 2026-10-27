#!/usr/bin/env python3
"""Independent small retrieval experiment. No network except explicit --download-model.

Run: python benchmarks/evaluate.py --work /tmp/ravel-eval --download-model
Worker runs use separate SQLite databases and processes for each configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Curated before measuring, with disjoint subjects across train and test.
# Each tuple: split, source type, source name, source text, exact query, intent query.
CASES = [
    (
        "train",
        "code",
        "auth",
        'def verify_secret(candidate, encoded):\n    """Check a password against a salted digest without timing leaks."""\n    import hmac\n    return hmac.compare_digest(candidate, encoded)\n',
        "verify_secret",
        "check whether a supplied password matches the stored digest",
    ),
    (
        "train",
        "code",
        "backoff",
        'def retry_delay(attempt):\n    """Increase the waiting interval exponentially after failed requests."""\n    return min(60, 2 ** attempt)\n',
        "retry_delay",
        "wait longer between repeated failures of a network request",
    ),
    (
        "train",
        "code",
        "billing",
        'def amount_due(lines, discount):\n    """Total invoice charges after applying a fractional price reduction."""\n    subtotal = sum(price * count for price, count in lines)\n    return subtotal * (1 - discount)\n',
        "amount_due",
        "calculate the final customer bill with a coupon",
    ),
    (
        "train",
        "code",
        "pagination",
        'def window(items, offset, count):\n    """Select a consecutive page from a collection."""\n    return items[offset:offset + count]\n',
        "window",
        "return the next page of records from a list",
    ),
    (
        "train",
        "code",
        "queue",
        'def drain_pending(queue):\n    """Consume all waiting jobs in first-in first-out order."""\n    while queue:\n        yield queue.pop(0)\n',
        "drain_pending",
        "process outstanding work in the order it arrived",
    ),
    (
        "train",
        "code",
        "csv",
        'def escape_field(value):\n    """Quote comma-separated output values containing delimiters or newlines."""\n    text = str(value).replace(chr(34), chr(34) * 2)\n    return chr(34) + text + chr(34)\n',
        "escape_field",
        "make spreadsheet cell text safe when it contains quotation marks",
    ),
    (
        "train",
        "code",
        "distance",
        'def manhattan(a, b):\n    """Sum absolute coordinate differences for a grid walking distance."""\n    return sum(abs(x - y) for x, y in zip(a, b))\n',
        "manhattan",
        "how far apart are two grid cells if diagonal moves are forbidden",
    ),
    (
        "train",
        "code",
        "memo",
        'def remember(key, compute, store):\n    """Reuse a previously calculated result or calculate it once."""\n    if key not in store:\n        store[key] = compute()\n    return store[key]\n',
        "remember",
        "avoid repeating expensive calculations for the same input",
    ),
    (
        "train",
        "doc",
        "backup",
        "# Snapshot rotation\nKeep seven daily copies and four weekly copies.\nVerify restoration in a separate directory before removing old archives.\nEncrypt portable media and store one copy off site.\n",
        "snapshot rotation",
        "recover files after accidental deletion from a laptop",
    ),
    (
        "train",
        "doc",
        "accessibility",
        "# Keyboard navigation\nEvery interactive control must accept focus.\nUse visible outlines and descriptive labels.\nDialogs return focus to their launching button after dismissal.\n",
        "keyboard navigation",
        "make an interface usable without a mouse",
    ),
    (
        "train",
        "doc",
        "incident",
        "# Service incident procedure\nRecord the first observed failure time.\nAssign one coordinator and collect logs without secrets.\nRestore availability before writing the retrospective.\n",
        "service incident procedure",
        "what should the team do during an outage",
    ),
    (
        "train",
        "doc",
        "privacy",
        "# Data minimization\nCollect only fields needed to fulfill the request.\nDelete expired records and restrict retention periods.\nDo not put personal identifiers in diagnostic logs.\n",
        "data minimization",
        "reduce how much customer information the application retains",
    ),
    (
        "test",
        "code",
        "atomic",
        'def replace_document(target, content):\n    """Write a temporary file then atomically rename it to prevent partial saves."""\n    temporary = target.with_suffix(".pending")\n    temporary.write_text(content)\n    temporary.replace(target)\n',
        "replace_document",
        "prevent readers from observing a partially written file",
    ),
    (
        "test",
        "code",
        "expiry",
        'def still_valid(created, now, lifetime):\n    """Determine whether a cached entry has outlived its time to live."""\n    return now - created < lifetime\n',
        "still_valid",
        "check if a stored response is too old to reuse",
    ),
    (
        "test",
        "code",
        "rate",
        'def take_token(bucket, now):\n    """A token bucket permits traffic bursts while limiting sustained request rate."""\n    tokens = min(bucket["capacity"], bucket["tokens"] + now - bucket["updated"])\n    return tokens >= 1\n',
        "take_token",
        "throttle clients that send too many requests",
    ),
    (
        "test",
        "code",
        "sanitize",
        'def safe_child(root, relative):\n    """Reject paths that escape the allowed root through parent traversal."""\n    candidate = (root / relative).resolve()\n    candidate.relative_to(root.resolve())\n    return candidate\n',
        "safe_child",
        "stop a supplied filename from accessing a parent directory",
    ),
    (
        "test",
        "code",
        "topology",
        'def ready_nodes(dependencies, completed):\n    """Find tasks whose prerequisites have already finished in a dependency graph."""\n    return [node for node, needs in dependencies.items() if set(needs) <= completed]\n',
        "ready_nodes",
        "which jobs can start after their prerequisite jobs finish",
    ),
    (
        "test",
        "code",
        "dedup",
        'def unique_ordered(values):\n    """Remove duplicate items while preserving their original order."""\n    return list(dict.fromkeys(values))\n',
        "unique_ordered",
        "eliminate repeated list entries without rearranging the remaining entries",
    ),
    (
        "test",
        "code",
        "stream",
        'def batches(iterator, size):\n    """Yield bounded groups from a stream without loading the entire dataset."""\n    from itertools import islice\n    while group := list(islice(iterator, size)):\n        yield group\n',
        "batches",
        "process a huge input incrementally with limited memory",
    ),
    (
        "test",
        "code",
        "checksum",
        'def fingerprint(content):\n    """Detect changes in raw bytes using a SHA256 content hash."""\n    import hashlib\n    return hashlib.sha256(content).hexdigest()\n',
        "fingerprint",
        "tell whether file contents changed even if the modification timestamp stayed the same",
    ),
    (
        "test",
        "doc",
        "keys",
        "# Signing key rotation\nCreate a replacement public key and publish its identifier.\nOverlap verification of old and new signatures during migration.\nRevoke the former key after all clients have updated.\n",
        "signing key rotation",
        "replace a compromised signature verification key safely",
    ),
    (
        "test",
        "doc",
        "restore",
        "# Database recovery\nRestore the last verified snapshot into a fresh database.\nReplay the transaction journal up to the desired recovery point.\nValidate row counts before switching application traffic.\n",
        "database recovery",
        "bring back a corrupted relational store without losing recent transactions",
    ),
    (
        "test",
        "doc",
        "offline",
        "# Disconnected operation\nStore edits in a local outbox when connectivity is unavailable.\nSend queued changes after reconnecting and resolve version conflicts.\nShow users which records are awaiting synchronization.\n",
        "disconnected operation",
        "allow people to keep working when the internet goes away",
    ),
    (
        "test",
        "doc",
        "release",
        "# Release verification\nInstall the built package in an empty environment.\nExercise the documented quickstart and compare checksums of uploaded artifacts.\nTag the exact source revision that passed the checks.\n",
        "release verification",
        "prove a distributed software package actually works for a new user",
    ),
]


def write_fixture(work):
    corpus = work / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    queries = []
    for split, kind, name, text, exact, intent in CASES:
        path = f"{'src' if kind == 'code' else 'notes'}/{name}.{'py' if kind == 'code' else 'md'}"
        target = corpus / path
        target.parent.mkdir(exist_ok=True)
        target.write_text(text)
        for qkind, query in [("exact", exact), ("intent", intent)]:
            queries.append(
                {
                    "id": f"{split}-{name}-{qkind}",
                    "split": split,
                    "kind": kind,
                    "query_type": qkind,
                    "query": query,
                    "gold": [path],
                    "token_budget": 1200 if qkind == "exact" else 4096,
                }
            )
    # Off-topic distractors are intentionally simple, so this is a smoke suite,
    # not an estimate of large production repository retrieval performance.
    for i, noun in enumerate(
        [
            "ocean",
            "garden",
            "music",
            "planet",
            "bread",
            "camera",
            "train",
            "volcano",
            "fabric",
            "painting",
            "bird",
            "chess",
        ]
    ):
        (corpus / "notes" / f"unrelated_{i:02}.md").write_text(
            f"# {noun.title()} observation\nA field notebook about {noun}, seasonal patterns, color, texture and observations.\nThis document records nontechnical observations from a weekend activity.\n"
        )
    (work / "queries.json").write_text(json.dumps(queries, indent=2) + "\n")
    return corpus, queries


def storage_bytes(root):
    """Avoid counting Hugging Face blob/snapshot symlink aliases repeatedly."""
    seen = set()
    unique = allocated = logical = 0
    for path in Path(root).rglob("*"):
        if path.is_file():
            st = path.stat()
            logical += st.st_size
            if (st.st_dev, st.st_ino) not in seen:
                seen.add((st.st_dev, st.st_ino))
                unique += st.st_size
                allocated += getattr(st, "st_blocks", 0) * 512
    return {"unique_bytes": unique, "allocated_bytes": allocated, "pathname_logical_bytes": logical}


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int((len(values) - 1) * p + 0.5)))] if values else 0


def rank_metrics(paths, gold):
    unique = list(dict.fromkeys(paths))
    hits = set(unique) & set(gold)
    return {
        "reciprocal_rank": next((1 / (i + 1) for i, p in enumerate(unique) if p in gold), 0),
        "recall_at_8": len(hits) / len(gold),
        "precision_returned": len(hits) / max(1, len(unique)),
    }


def worker(args):
    from ravel import Index
    from ravel.embeddings import LocalEmbedder

    work = Path(args.work)
    spec = json.loads(args.spec)
    queries = json.loads((work / "queries.json").read_text())
    begin = time.perf_counter()
    model_dir = Path(args.model_dir) if args.model_dir else work / "models"
    embedder = None if spec["mode"] == "lexical" else LocalEmbedder(model_dir)
    with Index(
        work / "corpus",
        db_path=work / f"{spec['name']}.sqlite3",
        cache_bytes=spec["cache_bytes"],
        embedder=embedder,
    ) as idx:
        scan = idx.sync()
        build_ms = (time.perf_counter() - begin) * 1000
        materialize_ms = 0
        if spec.get("materialize"):
            t = time.perf_counter()
            idx.materialize()
            materialize_ms = (time.perf_counter() - t) * 1000
        rows = []
        for q in queries:
            for repeat in range(args.repeats):
                result = idx.search(
                    q["query"],
                    mode=spec["mode"],
                    token_budget=q["token_budget"],
                    limit=8,
                    latency_ms=1000,
                    memory_kib=2048,
                    policy=spec.get("policy"),
                    refresh=True,
                )
                paths = [item["path"] for item in result["results"]]
                rows.append(
                    {
                        "query_id": q["id"],
                        "split": q["split"],
                        "query_type": q["query_type"],
                        "kind": q["kind"],
                        "repeat": repeat,
                        "paths": paths,
                        **rank_metrics(paths, q["gold"]),
                        "plan": result["plan"],
                        "metrics": result["metrics"],
                    }
                )
        stats = idx.stats()
        # No absolute local root in published output.
        stats.pop("root", None)
        before_compact = stats["index_bytes"]
        idx.compact()
        stats = {
            **stats,
            "index_bytes_before_compact": before_compact,
            "index_bytes_after_compact": idx.path.stat().st_size,
        }
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_bytes = rss if sys.platform == "darwin" else rss * 1024
        output = {
            "configuration": {k: v for k, v in spec.items() if k != "policy"},
            "rows": rows,
            "stats": stats,
            "startup_and_lexical_index_ms": round(build_ms, 3),
            "materialize_ms": round(materialize_ms, 3),
            "initial_scan": scan,
            "process_peak_rss_bytes": rss_bytes,
            "source_sha256": {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                for p in [
                    "src/ravel/engine.py",
                    "src/ravel/planner.py",
                    "src/ravel/embeddings.py",
                    "src/ravel/sources.py",
                ]
            },
            "process_cpu_seconds": round(
                resource.getrusage(resource.RUSAGE_SELF).ru_utime
                + resource.getrusage(resource.RUSAGE_SELF).ru_stime,
                3,
            ),
        }
        Path(args.output).write_text(json.dumps(output, indent=2) + "\n")


def summarize(run):
    rows = [r for r in run["rows"] if r["split"] == "test"]
    first = [r for r in rows if r["repeat"] == 0]
    warm = [r for r in rows if r["repeat"] > 0]
    return {
        "name": run["configuration"]["name"],
        "test_queries": len(first),
        "mrr": round(statistics.mean(r["reciprocal_rank"] for r in first), 4),
        "recall_at_8": round(statistics.mean(r["recall_at_8"] for r in first), 4),
        "precision_returned": round(statistics.mean(r["precision_returned"] for r in first), 4),
        "first_query_p50_ms": round(percentile([r["metrics"]["elapsed_ms"] for r in first], 0.5), 3),
        "first_query_p95_ms": round(percentile([r["metrics"]["elapsed_ms"] for r in first], 0.95), 3),
        "warm_p50_ms": round(percentile([r["metrics"]["elapsed_ms"] for r in warm], 0.5), 3),
        "warm_p95_ms": round(percentile([r["metrics"]["elapsed_ms"] for r in warm], 0.95), 3),
        "mean_context_byte_upper_bound": round(
            statistics.mean(r["metrics"]["tokens_used"] for r in first), 1
        ),
        "mean_semantic_coverage": round(statistics.mean(r["metrics"]["semantic_coverage"] for r in first), 4),
        "cache_hits": sum(r["metrics"]["cache_hits"] for r in rows),
        "cache_misses": sum(r["metrics"]["cache_misses"] for r in rows),
        "latency_target_exceeded_queries": sum(r["metrics"]["latency_target_exceeded"] for r in first),
        "index_bytes": run["stats"]["index_bytes_after_compact"],
        "vector_bytes": run["stats"]["cache_bytes"],
        "peak_rss_bytes": run["process_peak_rss_bytes"],
        "startup_and_lexical_index_ms": run["startup_and_lexical_index_ms"],
        "materialize_ms": run["materialize_ms"],
        "process_cpu_seconds": run["process_cpu_seconds"],
    }


def freshness(work):
    from ravel import Index

    root = work / "freshness"
    root.mkdir(exist_ok=True)
    source = root / "original.py"
    source.write_text('def old_signal():\n    return "former"\n')
    checks = {}
    with Index(root) as idx:
        t = time.perf_counter()
        idx.sync()
        checks["initial_ms"] = (time.perf_counter() - t) * 1000
        source.write_text('def new_signal():\n    return "replacement"\n')
        t = time.perf_counter()
        edited = idx.search("new_signal")
        checks["edit_ms"] = (time.perf_counter() - t) * 1000
        checks["edit_new_found"] = any(r["symbol"] == "new_signal" for r in edited["results"])
        checks["edit_old_absent"] = all(
            r["symbol"] != "old_signal" and "former" not in r["text"]
            for r in idx.search("old_signal")["results"]
        )
        source.rename(root / "renamed.py")
        renamed = idx.search("new_signal")
        renamed_symbol = [r for r in renamed["results"] if r["symbol"] == "new_signal"]
        checks["rename_new_path_only"] = bool(renamed_symbol) and all(
            r["path"] == "renamed.py" for r in renamed_symbol
        )
        (root / "renamed.py").unlink()
        checks["delete_absent"] = all(
            r["symbol"] != "new_signal" and "replacement" not in r["text"]
            for r in idx.search("new_signal")["results"]
        )
        (root / "added.md").write_text("# newlyaddeduniqueterm\nA new document.\n")
        checks["add_found"] = bool(idx.search("newlyaddeduniqueterm")["results"])
    return checks


def official_contextbench(args):
    """A single frozen-repo file-retrieval diagnostic, not official agent scoring."""
    import pyarrow.parquet as pq
    import re
    from ravel import Index
    from ravel.embeddings import LocalEmbedder

    metadata = Path(args.contextbench_parquet)
    rows = pq.read_table(metadata).to_pylist()
    row = next(r for r in rows if r["instance_id"] == args.instance)
    gold = sorted(set(re.findall(r"file:\s*([^\n]+)", row["gold_context"])))
    if any(p.startswith("/") for p in gold):
        raise SystemExit("This diagnostic expects repository-relative gold paths.")
    snapshot = Path(args.snapshot).resolve()
    if any(not (snapshot / p).is_file() for p in gold):
        raise SystemExit("Snapshot is missing a gold source path; refuse to score.")
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    embedder = LocalEmbedder(Path(args.model_dir))
    outputs = []
    for mode in ["lexical", "hybrid", "auto"]:
        db = work / f"official-{mode}.sqlite3"
        if db.exists():
            raise SystemExit("Use a fresh official work directory to preserve prior databases.")
        with Index(snapshot, db_path=db, cache_bytes=8 * 1024 * 1024, embedder=embedder) as idx:
            initial = idx.sync()
            measured = []
            for repeat in range(args.repeats):
                result = idx.search(
                    row["problem_statement"],
                    mode=mode,
                    limit=20,
                    token_budget=32000,
                    latency_ms=3000,
                    memory_kib=4096,
                )
                paths = [r["path"] for r in result["results"]]
                measured.append(
                    {
                        "repeat": repeat,
                        "paths": paths,
                        "reciprocal_rank": rank_metrics(paths, gold)["reciprocal_rank"],
                        "file_recall_returned": len(set(paths) & set(gold)) / len(gold),
                        "delivered_spans": [
                            {
                                "path": r["path"],
                                "start_line": r["start_line"],
                                "end_line": r["end_line"],
                                "sha256": r["sha256"],
                            }
                            for r in result["results"]
                        ],
                        "plan": result["plan"],
                        "metrics": result["metrics"],
                    }
                )
            stats = idx.stats()
            stats.pop("root", None)
            outputs.append({"mode": mode, "initial_sync": initial, "stats": stats, "rows": measured})
    report = {
        "scope": "one predeclared ContextBench test task, static file-retrieval diagnostic; not official agent/line-level scoring or a leaderboard result",
        "selection": "first xarray test-set task; chosen before running retrieval to bound source download and compute",
        "dataset": "Contextbench/ContextBench data/test.parquet",
        "metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
        "instance_id": row["instance_id"],
        "original_inst_id": row["original_inst_id"],
        "repo": row["repo"],
        "base_commit": row["base_commit"],
        "snapshot_url": f"https://codeload.github.com/{row['repo']}/tar.gz/{row['base_commit']}",
        "query_sha256": hashlib.sha256(row["problem_statement"].encode()).hexdigest(),
        "query_characters": len(row["problem_statement"]),
        "gold_paths": gold,
        "results": outputs,
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in [
                "src/ravel/engine.py",
                "src/ravel/planner.py",
                "src/ravel/embeddings.py",
                "src/ravel/sources.py",
            ]
        },
        "limitations": [
            "only one task",
            "eligible text files only, unlike official agent exploring arbitrary files",
            "no fixes or tests executed",
            "token packing uses byte upper bound, not official tokenizer",
            "no patch or gold-context text used as search input",
            "archive revision supplied externally; result revision remains null without .git",
            "semantic auto scans partial cold corpus under 3-second soft target",
        ],
    }
    result_dir = ROOT / "benchmarks" / "results"
    result_dir.mkdir(exist_ok=True)
    (result_dir / "contextbench-diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "instance_id": row["instance_id"],
                "gold_paths": gold,
                "results": [
                    {
                        "mode": o["mode"],
                        "rows": [
                            {
                                "reciprocal_rank": r["reciprocal_rank"],
                                "file_recall_returned": r["file_recall_returned"],
                                "elapsed_ms": r["metrics"]["elapsed_ms"],
                                "semantic_coverage": r["metrics"]["semantic_coverage"],
                            }
                            for r in o["rows"]
                        ],
                    }
                    for o in outputs
                ],
            },
            indent=2,
        )
    )


def budget_sweep(args):
    from ravel import Index
    from ravel.embeddings import LocalEmbedder
    import sqlite3

    work = Path(args.work)
    seed = work / "semantic_full.sqlite3"
    target = work / "budget-sweep.sqlite3"
    if target.exists():
        raise SystemExit("Budget sweep database already exists; preserve it and use another work directory.")
    with sqlite3.connect(seed) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
    queries = json.loads((work / "queries.json").read_text())
    selected = [
        q
        for q in queries
        if q["id"]
        in {"test-atomic-intent", "test-expiry-intent", "test-offline-intent", "test-release-intent"}
    ]
    rows = []
    embedder = LocalEmbedder(Path(args.model_dir))
    with Index(work / "corpus", db_path=target, embedder=embedder) as idx:
        for latency in [25, 200, 1000]:
            for memory in [64, 2048]:
                for budget in [1200, 4096]:
                    for q in selected:
                        for repeat in range(args.repeats):
                            result = idx.search(
                                q["query"],
                                latency_ms=latency,
                                memory_kib=memory,
                                token_budget=budget,
                                mode="auto",
                                limit=8,
                            )
                            paths = [r["path"] for r in result["results"]]
                            rows.append(
                                {
                                    "query_id": q["id"],
                                    "latency_ms": latency,
                                    "memory_kib": memory,
                                    "token_budget": budget,
                                    "repeat": repeat,
                                    "paths": paths,
                                    **rank_metrics(paths, q["gold"]),
                                    "plan": result["plan"],
                                    "metrics": result["metrics"],
                                }
                            )
        stats = idx.stats()
        stats.pop("root", None)
    out = {
        "scope": "predeclared four held-out intent queries, warm full-vector cache, budget sweep; candidate memory is not process memory",
        "rows": rows,
        "stats": stats,
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in [
                "src/ravel/engine.py",
                "src/ravel/planner.py",
                "src/ravel/embeddings.py",
                "src/ravel/sources.py",
            ]
        },
    }
    (ROOT / "benchmarks" / "results" / "budget-sweep.json").write_text(json.dumps(out, indent=2) + "\n")
    print("Saved budget sweep", len(rows), "query runs")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True, help="fresh disposable work directory")
    ap.add_argument(
        "--download-model", action="store_true", help="explicitly allow free public model download"
    )
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--budget-sweep", action="store_true")
    ap.add_argument("--contextbench-parquet")
    ap.add_argument("--snapshot")
    ap.add_argument("--model-dir")
    ap.add_argument("--instance", default="SWE-Bench-Verified__python__maintenance__bugfix__90532e38")
    ap.add_argument("--spec")
    ap.add_argument("--output")
    args = ap.parse_args()
    if args.worker:
        worker(args)
        return
    if args.contextbench_parquet:
        official_contextbench(args)
        return
    if args.budget_sweep:
        budget_sweep(args)
        return
    work = Path(args.work).resolve()
    if work.exists() and any(work.iterdir()):
        raise SystemExit("Use a fresh empty --work directory; prior results are preserved.")
    work.mkdir(parents=True, exist_ok=True)
    _, queries = write_fixture(work)
    from ravel.embeddings import LocalEmbedder, MODEL
    from ravel.planner import train, FEATURES

    t = time.perf_counter()
    model_dir = Path(args.model_dir) if args.model_dir else work / "models"
    LocalEmbedder(model_dir, download=args.download_model)
    model_setup_ms = (time.perf_counter() - t) * 1000
    result_dir = ROOT / "benchmarks" / "results"
    result_dir.mkdir(exist_ok=True)
    runs = []

    def run(spec):
        out = work / f"{spec['name']}.json"
        subprocess.run(
            [
                sys.executable,
                __file__,
                "--worker",
                "--work",
                str(work),
                "--spec",
                json.dumps(spec),
                "--output",
                str(out),
                "--repeats",
                str(args.repeats),
                "--model-dir",
                str(model_dir),
            ],
            check=True,
        )
        raw = json.loads(out.read_text())
        (result_dir / f"{spec['name']}.json").write_text(json.dumps(raw, indent=2) + "\n")
        runs.append(raw)
        print(json.dumps(summarize(raw)), flush=True)
        return raw

    for mode in ["lexical", "hybrid", "semantic"]:
        run(
            {
                "name": f"{mode}_full",
                "mode": mode,
                "cache_bytes": 8 * 1024 * 1024,
                "materialize": mode != "lexical",
            }
        )
    train_ids = [q["id"] for q in queries if q["split"] == "train"]
    labels = []
    label_evidence = []
    for qid in train_ids:
        options = []
        for run_data in runs:
            matches = [r for r in run_data["rows"] if r["query_id"] == qid]
            rr = statistics.mean(r["reciprocal_rank"] for r in matches)
            ms = statistics.median(r["metrics"]["elapsed_ms"] for r in matches)
            budget = matches[0]["plan"]["token_budget"]
            tokens = statistics.mean(r["metrics"]["tokens_used"] for r in matches)
            utility = rr - 0.05 * min(ms / 1000, 2) - 0.02 * tokens / budget
            options.append(
                {
                    "action": run_data["configuration"]["mode"],
                    "utility": utility,
                    "rr": rr,
                    "median_ms": ms,
                    "context_byte_upper_bound": tokens,
                }
            )
        best = max(options, key=lambda x: x["utility"])
        feat = next(r for r in runs[0]["rows"] if r["query_id"] == qid)["plan"]["features"]
        # Features describe a fully populated cache for both policies. Labels
        # derive from measured training actions only; test queries are excluded.
        feat["cache_coverage"] = 1.0
        labels.append({"features": [feat[k] for k in FEATURES], "action": best["action"]})
        label_evidence.append({"query_id": qid, "options": options, "selected": best["action"]})
    policy = train(labels)
    policy_path = work / "learned-policy.json"
    policy_path.write_text(json.dumps(policy, indent=2) + "\n")
    (result_dir / "learned-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    (result_dir / "training-labels.json").write_text(
        json.dumps(
            {
                "formula": "RR - 0.05*min(median_latency_ms/1000,2) - 0.02*context_bytes/token_budget",
                "rows": label_evidence,
            },
            indent=2,
        )
        + "\n"
    )
    run({"name": "heuristic_full", "mode": "auto", "cache_bytes": 8 * 1024 * 1024, "materialize": True})
    run({"name": "heuristic_small", "mode": "auto", "cache_bytes": 1552, "materialize": False})
    run({"name": "heuristic_nocache", "mode": "auto", "cache_bytes": 0, "materialize": False})
    run(
        {
            "name": "learned_full",
            "mode": "auto",
            "cache_bytes": 8 * 1024 * 1024,
            "materialize": True,
            "policy": str(policy_path),
        }
    )
    hashes = {
        p.relative_to(work / "corpus").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (work / "corpus").rglob("*")
        if p.is_file()
    }
    report = {
        "scope": "developer-authored 48-query smoke experiment; 24 train, 24 subject-disjoint test; not an official benchmark score",
        "model": MODEL,
        "model_bytes": storage_bytes(model_dir)["unique_bytes"],
        "model_storage": storage_bytes(model_dir),
        "model_setup_ms": round(model_setup_ms, 3),
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "macos_version": platform.mac_ver()[0],
        "logical_cpu_count": os.cpu_count(),
        "repeats": args.repeats,
        "latency_ms": 1000,
        "candidate_memory_kib": 2048,
        "corpus_files": len(hashes),
        "source_bytes": sum(p.stat().st_size for p in (work / "corpus").rglob("*") if p.is_file()),
        "corpus_hashes": hashes,
        "summary": [summarize(r) for r in runs],
        "freshness": freshness(work),
        "cold_definition": "separate process per configuration; model load+sync counted as startup; first query per test query is mixed-cache, not OS disk cold",
        "token_accounting": "serialized result UTF-8 byte count, conservative token upper bound; not model-specific token count",
        "measured_source_sha256": runs[0]["source_sha256"],
        "all_workers_same_source": all(r["source_sha256"] == runs[0]["source_sha256"] for r in runs),
        "limits": [
            "tiny authored corpus; easy off-topic distractors",
            "same-process train queries warm caches before held-out test",
            "semantic uncached work is sampled under depth/deadline; full cached scan supported; coverage reported",
            "cache budget governs vector payload only, not total SQLite/model/RSS",
            "no GPU use or end-to-end coding-task success measured",
        ],
    }
    (result_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (ROOT / "benchmarks" / "queries.json").write_text(json.dumps(queries, indent=2) + "\n")
    print("Saved raw results and summary.")


if __name__ == "__main__":
    main()
