from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from . import __version__
from .engine import Index


def main(argv=None):
    # Source text and the MCP wire format are UTF-8 on every platform, including
    # Windows pipes whose default encoding can otherwise be a legacy code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ravel", description="The right context. Almost no overhead.")
    parser.add_argument("--version", action="version", version=f"ravel {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("index", help="Index or incrementally refresh a local directory")
    p.add_argument("path", nargs="?", default=None)
    p.add_argument("--semantic", action="store_true", help="Enable the optional local ONNX model")
    p.add_argument("--download-model", action="store_true", help="Explicitly allow a one-time public model download")
    p.add_argument("--materialize", action="store_true", help="Precompute vectors up to the cache quota")
    p.add_argument("--compact", action="store_true", help="Reclaim SQLite free pages after deletions")
    p = commands.add_parser("search", help="Retrieve fresh, source-linked evidence")
    p.add_argument("query")
    p.add_argument("--tokens", type=int, default=2048, help="Evidence token upper bound, conservatively charged by UTF-8 bytes")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--mode", choices=["auto", "lexical", "hybrid", "semantic"], default="auto")
    p.add_argument("--latency-ms", type=float, default=200, help="Soft target; source verification/model cold start may exceed it")
    p.add_argument("--memory-kib", type=int, default=2048, help="Candidate working-set allowance, not process RSS")
    p.add_argument("--policy", type=Path, help="Opt-in learned selector JSON")
    p.add_argument("--snapshot", action="store_true", help="Skip freshness scan; results are explicitly marked unchecked")
    p = commands.add_parser("symbols", help="Find Python AST symbols by exact name or prefix")
    p.add_argument("name", nargs="?", default="")
    commands.add_parser("stats", help="Inspect storage, source provenance and model overhead")
    commands.add_parser("mcp", help="Serve this approved root over MCP stdio")
    p = commands.add_parser("inspect", help="Open a loopback interactive index inspector")
    p.add_argument("--port", type=int, default=8765)
    p = commands.add_parser("train-policy", help="Fit an opt-in tiny policy from measured action labels")
    p.add_argument("data", type=Path)
    p.add_argument("output", type=Path)
    for p in commands.choices.values():
        p.add_argument("--root", default=".", help="Approved source directory")
        p.add_argument("--cache-mb", type=float, default=None, help="Int8 vector payload quota; SQLite/model overhead reported separately")
        p.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)
    try:
        if args.cache_mb is not None and (not math.isfinite(args.cache_mb) or args.cache_mb < 0):
            raise ValueError("--cache-mb must be finite and nonnegative")
        options = {"cache_bytes": int(args.cache_mb * 1024 * 1024) if args.cache_mb is not None else None}
        if args.command == "mcp":
            from .server import mcp
            return mcp(args.root, **options)
        if args.command == "inspect":
            from .server import inspect
            return inspect(args.root, args.port, **options)
        if args.command == "train-policy":
            from .planner import train
            model = train(json.loads(args.data.read_text()))
            args.output.write_text(json.dumps(model, indent=2) + "\n")
            print(f"Saved policy trained on {model['training_rows']} measured rows")
            return 0
        root = (args.path or args.root) if args.command == "index" else args.root
        with Index(root, **options) as index:
            if args.command == "index":
                if args.download_model and not args.semantic:
                    raise ValueError("--download-model requires --semantic")
                if args.semantic:
                    index.enable_semantic(download=args.download_model)
                payload = {"update": index.sync()}
                if args.materialize:
                    payload["materialization"] = index.materialize()
                if args.compact:
                    index.compact()
                payload["stats"] = index.stats()
            elif args.command == "stats":
                payload = index.stats()
            elif args.command == "symbols":
                index.sync()
                rows = index.db.execute("SELECT DISTINCT path,symbol,start_line,end_line,calls FROM chunks "
                                        "WHERE symbol != '' AND (symbol=? OR symbol LIKE ? ESCAPE '\\') "
                                        "ORDER BY symbol,path,start_line LIMIT 100", (args.name, args.name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"))
                payload = [dict(r) for r in rows]
            else:
                payload = index.search(args.query, token_budget=args.tokens, limit=args.limit, mode=args.mode,
                                       latency_ms=args.latency_ms, memory_kib=args.memory_kib, policy=args.policy,
                                       refresh=not args.snapshot)
            if args.json or args.command != "search":
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(f"RAVEL  {payload['plan']['strategy']}  {payload['metrics']['elapsed_ms']:.1f} ms  "
                      f"{payload['metrics']['tokens_used']}/{args.tokens} context budget")
                print(payload["plan"]["reason"] + "\n")
                for r in payload["results"]:
                    print(f"{r['path']}:{r['start_line']}-{r['end_line']}" + (f"  [{r['symbol']}]" if r["symbol"] else ""))
                    print(r["text"] + "\n")
                if not payload["results"]:
                    print("No evidence fits. Try a larger --tokens budget, different query or enabled semantic mode.")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ravel: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
