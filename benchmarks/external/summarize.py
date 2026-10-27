"""Recompute honest file-level hit/MRR and latency summaries from raw runs."""

from pathlib import Path
import json
import math
import statistics

root = Path(__file__).parent
rows = []
for p in sorted(root.glob("*.json")):
    data = json.loads(p.read_text())
    if not isinstance(data, dict) or not data.get("queries"):
        continue
    queries = data["queries"]
    latencies = sorted(q["latency_ms"] for q in queries)
    row = {
        "run": p.name,
        "queries": len(queries),
        "index_bytes": data.get("index_bytes"),
        "p50_ms": statistics.median(latencies),
        "p95_ms": latencies[math.ceil(0.95 * len(latencies)) - 1],
        "error_count": sum(bool(q.get("parse_error") or q.get("returncode", 0)) for q in queries),
    }
    for kind in ["all", "natural", "identifier"]:
        subset = [q for q in queries if kind == "all" or q["kind"] == kind]
        ranks = [
            next((i + 1 for i, f in enumerate(q["files"][:5]) if f in q["relevant"]), None) for q in subset
        ]
        row[kind] = {
            "n": len(subset),
            "hit_at_1": sum(r == 1 for r in ranks) / len(ranks),
            "hit_at_5": sum(r is not None for r in ranks) / len(ranks),
            "mrr_at_5": sum(1 / r if r else 0 for r in ranks) / len(ranks),
        }
    rows.append(row)
(root / "summary.json").write_text(json.dumps(rows, indent=2))
for r in rows:
    print(r["run"], r["all"]["hit_at_1"], round(r["p50_ms"], 2), round(r["p95_ms"], 2), r["index_bytes"])
