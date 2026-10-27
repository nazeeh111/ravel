# RAVEL v0.1.0

The right context. Almost no overhead.

RAVEL is an experimental local-first code and document context engine, with a
small model-free SQLite/BM25 core and optional pinned local BGE/ONNX embeddings.

- CLI, reusable Python API, source-linked evidence and stdio MCP for Codex/Claude Code.
- Content-hash incremental freshness, Python AST symbols, exact phrases and explicit source hashes/revisions.
- Adaptive retrieval, int8 vectors, persisted storage quotas and measured frequency/cost-aware caching.
- A local interactive inspector, original editable SVG branding and a genuine 18-second screenshot demo.
- 24 local correctness/privacy tests, independent review and official MCP-client interoperability.
- Reproducible held-out heuristic/learned experiments, executed LEANN/QMD/Codanna/grepai/FAISS comparisons, and one full-repository ContextBench diagnostic.

Install the attached wheel with `python -m pip install ./ravel_index-0.1.0-py3-none-any.whl`,
or use the one-command Git installation in the README. The source archive is also attached.
`SHA256SUMS` covers all separately uploaded release artifacts.

Important limits: this is an alpha, not a universal performance claim. LEANN and
FAISS produced smaller indexes on the shared tiny corpus. Several competitors
matched perfect retrieval. Learned selection tied heuristic quality in the small
held-out suite; host-load variation does not establish a reliable latency winner.
Full public benchmark leaderboards and downstream coding-agent success rates are
unmeasured. Latency is a soft target, candidate memory is not process RSS, and
context budgets conservatively count evidence bytes rather than exact model tokens.
See the README and benchmark reports for configurations, raw data and failures.

No paid APIs, source telemetry or hosted models. Optional model downloads are explicit.
Source excerpts remain on the local machine. MIT licensed with dependency attribution.
