"""Run installed external CLIs on fresh copies of an identical fixture.

Runtime locations are explicit CLI args; no installs or global configuration edits.
Reports include CLI startup and warm filesystem/model cache, not warm-server timings.
"""

from pathlib import Path
import argparse
import os
import json
import subprocess
import time
import platform
import re
from fixture import make


def run(argv, cwd, env):
    start = time.perf_counter()
    p = subprocess.run(
        ["/usr/bin/time", "-l", *map(str, argv)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    elapsed = (time.perf_counter() - start) * 1000
    m = re.search(r"(\d+)\s+maximum resident set size", p.stderr)
    cpu = re.search(r"([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys", p.stderr)
    return {
        "returncode": p.returncode,
        "latency_ms": elapsed,
        "peak_rss_bytes": int(m[1]) if m else None,
        "cpu_seconds": float(cpu[2]) + float(cpu[3]) if cpu else None,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path(__file__).parent)
    ap.add_argument("--only", choices=["qmd", "codanna", "grepai"])
    a = ap.parse_args()
    base = a.tools
    out = a.output
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TOKENIZERS_PARALLELISM"] = "false"
    env["GGML_METAL_NO_RESIDENCY"] = "1"
    env["QMD_FORCE_CPU"] = "1"
    env["XDG_CONFIG_HOME"] = str(base / "qmd-config")
    env["XDG_CACHE_HOME"] = str(base / "qmd-cache")
    codanna = next((base / "codanna").rglob("codanna"))
    grepai = base / "grepai" / "grepai"
    qmd = ["node", base / "qmd" / "dist/cli/qmd.js"]
    for name in [a.only] if a.only else ["qmd", "codanna", "grepai"]:
        corpus = base / ("measured-" + name)
        if corpus.exists():
            raise SystemExit(
                f"Refusing to replace existing {corpus}; choose a fresh tools directory or archive it manually"
            )
        rows = make(corpus)
        if name == "qmd":
            # A new named index does not reuse the earlier exploratory document index.
            pre = qmd + ["--index", "ravel-measured"]
            build = pre + [
                "collection",
                "add",
                str(corpus),
                "--name",
                "ravel-fixture",
                "--mask",
                "**/*.{md,py}",
            ]
            modes = ["bm25"]
        elif name == "codanna":
            run([codanna, "init"], corpus, env)
            cfg = corpus / ".codanna/settings.toml"
            cfg.write_text(cfg.read_text().replace("threshold = 0.6", "threshold = 0.0"))
            build = [codanna, "index", "."]
            modes = ["semantic"]
        else:
            run([grepai, "init", "--yes"], corpus, env)
            cfg = corpus / ".grepai/config.yaml"
            cfg.write_text(
                cfg.read_text()
                .replace("nomic-embed-text", "all-minilm")
                .replace("dimensions: 768", "dimensions: 384")
            )
            build = [grepai, "index"]
            modes = ["semantic"]
        indexed = run(build, corpus, env)
        if indexed["returncode"]:
            print(name, "index failed", indexed["stderr"])
            continue
        for mode in modes:
            results = []
            for row in rows:
                if name == "qmd":
                    cmd = pre + ["search", row["query"], "--json", "-n", "5"]
                elif name == "codanna":
                    cmd = [
                        codanna,
                        "mcp",
                        "semantic_search_docs",
                        "query:" + row["query"],
                        "limit:5",
                        "--json",
                    ]
                else:
                    cmd = [grepai, "search", row["query"], "--json", "--limit", "5"]
                r = run(cmd, corpus, env)
                try:
                    raw = json.loads(r.pop("stdout"))
                    if name == "qmd":
                        files = [Path(x["file"].split("?", 1)[0]).name for x in raw]
                    elif name == "codanna":
                        files = [x["symbol"]["file_path"] for x in raw.get("data", [])]
                    else:
                        files = [x["file_path"] for x in raw]
                except Exception as e:
                    files = []
                    r["parse_error"] = str(e)
                r.pop("stderr", None)
                results.append({**row, **r, "files": files})
            root = (
                corpus / (".codanna" if name == "codanna" else ".grepai")
                if name != "qmd"
                else base / "qmd-cache" / "qmd"
            )
            # QMD named index only, exclude exploratory index + model files.
            disk = sum(
                p.stat().st_size
                for p in root.rglob("*")
                if p.is_file() and (name != "qmd" or p.name.startswith("ravel-measured.sqlite"))
            )
            indexed.pop("stdout", None)
            indexed.pop("stderr", None)
            report = {
                "tool": name,
                "mode": mode,
                "hardware": {"system": platform.system(), "machine": platform.machine()},
                "corpus_files": 32,
                "corpus_bytes": sum(p.stat().st_size for p in corpus.iterdir() if p.suffix in [".py", ".md"]),
                "index": indexed,
                "index_bytes": disk,
                "query_timing": "fresh CLI process per query, OS/model cache warm; includes startup",
                "queries": results,
            }
            (out / (name + "-" + mode + ".json")).write_text(json.dumps(report, indent=2))
            print(name, "done", disk, flush=True)


if __name__ == "__main__":
    main()
