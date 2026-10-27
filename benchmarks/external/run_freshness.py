"""Explicit incremental-update smoke tests on the disposable external fixtures.

Run after quality measurements. Only mutates generated retry/lease fixture files.
"""

from pathlib import Path
import argparse
import json
import os
from run_cli import run

ap = argparse.ArgumentParser()
ap.add_argument("--tools", type=Path, required=True)
ap.add_argument("--output", type=Path, default=Path(__file__).parent)
a = ap.parse_args()
base = a.tools
env = os.environ.copy()
env.update(XDG_CONFIG_HOME=str(base / "qmd-config"), XDG_CACHE_HOME=str(base / "qmd-cache"))
qmd = ["node", base / "qmd/dist/cli/qmd.js", "--index", "ravel-measured"]
codanna = next((base / "codanna").rglob("codanna"))
grepai = base / "grepai/grepai"
reports = []
for name in ["qmd", "codanna", "grepai"]:
    root = base / ("measured-" + name)
    if not (root / "lease.py").exists() or not (root / "retry.md").exists():
        raise SystemExit("Refusing to mutate already-changed fixture " + str(root))
    (root / "retry.py").write_text(
        'def refreshed_retry_request(value):\n    """Refreshed implementation for temporary network failures."""\n    return value\n'
    )
    (root / "retry.md").unlink()
    (root / "lease.py").rename(root / "lease_renamed.py")
    update = run(
        qmd + ["update"]
        if name == "qmd"
        else [codanna, "index", "."]
        if name == "codanna"
        else [grepai, "index"],
        root,
        env,
    )
    update.pop("stdout", None)
    update.pop("stderr", None)
    rows = []
    for query in ["refreshed_retry_request", "renew_lease"]:
        cmd = (
            qmd + ["search", query, "--json", "-n", "10"]
            if name == "qmd"
            else [codanna, "mcp", "semantic_search_docs", "query:" + query, "limit:10", "--json"]
            if name == "codanna"
            else [grepai, "search", query, "--json", "--limit", "10"]
        )
        r = run(cmd, root, env)
        raw = json.loads(r.pop("stdout"))
        r.pop("stderr", None)
        if name == "qmd":
            files = [Path(x["file"].split("?", 1)[0]).name for x in raw]
        elif name == "codanna":
            files = [x["symbol"]["file_path"] for x in raw.get("data", [])]
        else:
            files = [x["file_path"] for x in raw]
        rows.append({"query": query, "files": files, **r})
    files = [f for r in rows for f in r["files"]]
    reports.append(
        {
            "tool": name,
            "update": update,
            "new_name_found": "retry.py" in rows[0]["files"],
            "renamed_path_found": "lease_renamed.py" in rows[1]["files"],
            "deleted_path_absent": "retry.md" not in files,
            "old_renamed_path_absent": "lease.py" not in files,
            "queries": rows,
        }
    )
(a.output / "freshness.json").write_text(json.dumps(reports, indent=2))
print(json.dumps(reports, indent=2))
