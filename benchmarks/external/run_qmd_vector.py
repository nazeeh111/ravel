"""Run after run_cli.py to add QMD default vector-only measurements."""

from pathlib import Path
import os
import json
import argparse
from run_cli import run

ap = argparse.ArgumentParser()
ap.add_argument("--tools", type=Path, required=True)
ap.add_argument("--output", type=Path, default=Path(__file__).parent)
a = ap.parse_args()
base = a.tools
env = os.environ.copy()
env.update(
    XDG_CONFIG_HOME=str(base / "qmd-config"),
    XDG_CACHE_HOME=str(base / "qmd-cache"),
    QMD_FORCE_CPU="1",
    GGML_METAL_NO_RESIDENCY="1",
)
pre = ["node", base / "qmd/dist/cli/qmd.js", "--index", "ravel-measured"]
corpus = base / "measured-qmd"
indexed = run(pre + ["embed"], corpus, env)
if indexed["returncode"]:
    raise SystemExit(indexed["stderr"])
results = []
for row in json.loads((a.output / "queries.json").read_text()):
    r = run(pre + ["query", "vec: " + row["query"], "--no-rerank", "--json", "-n", "5"], corpus, env)
    try:
        files = [Path(x["file"].split("?", 1)[0]).name for x in json.loads(r.pop("stdout"))]
    except Exception as e:
        files = []
        r["parse_error"] = str(e)
    r.pop("stderr", None)
    results.append({**row, **r, "files": files})
    print("query", len(results), flush=True)
indexed.pop("stdout", None)
indexed.pop("stderr", None)
report = json.loads((a.output / "qmd-bm25.json").read_text())
report.update(mode="vector", embedding=indexed, queries=results)
report["index_bytes"] = sum(p.stat().st_size for p in (base / "qmd-cache/qmd").glob("ravel-measured.sqlite*"))
(a.output / "qmd-vector.json").write_text(json.dumps(report, indent=2))
print("qmd vector done")
