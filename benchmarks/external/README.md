# External retrieval microbenchmark

These are **executed product smoke tests**, not a large-scale retrieval leaderboard.
The independent hand-written fixture has 16 topics, each represented by one Python
function and one Markdown document (32 files, 32 queries). Functions are retrieval
fixtures, not implementations of the described algorithms. Natural-language
questions and exact identifiers have equal weight. Either corresponding file is
relevant. No source from a private repository is used.

Raw per-query JSON includes actual returned file paths, timings and errors. Run
`summarize.py` to derive hit@1, hit@5, MRR@5 and nearest-rank p95. It performs no
query rewriting or label training. The query suite is separate from RAVEL's
planner-training/evaluation suite, but small and easy enough to saturate several
systems. It does not measure actual coding-agent task success.

## Reproduce on macOS arm64

Requires Python 3.12+, Node, Bun, uv, git and a user-managed local Ollama server.
Use disposable non-synced storage. No hosted model or paid API is required.
The pinned binary archives are verified against recorded SHA-256 digests.

```sh
python3 benchmarks/external/prepare.py /tmp/ravel-comparison
uv pip install --python /tmp/ravel-comparison/leann-env/bin/python --no-deps -e .
uv pip install --python /tmp/ravel-comparison/leann-env/bin/python 'pathspec>=0.12.1,<1'
# With your local Ollama server running, explicitly download the free model:
ollama pull all-minilm
python3 benchmarks/external/run_cli.py --tools /tmp/ravel-comparison
python3 benchmarks/external/run_qmd_vector.py --tools /tmp/ravel-comparison
/tmp/ravel-comparison/leann-env/bin/python benchmarks/external/run_leann.py --work /tmp/ravel-comparison
/tmp/ravel-comparison/leann-env/bin/python benchmarks/external/run_ravel.py --work /tmp/ravel-comparison
python3 benchmarks/external/run_freshness.py --tools /tmp/ravel-comparison
python3 benchmarks/external/summarize.py
```

The embedding scripts download their public models on first use. LEANN/FAISS
model preparation is outside timed indexing; raw metadata records its time and
model bytes. QMD's embedding command records its own duration. CLI initial
indexing includes any engine initialization and cache setup. `run_ravel.py` injects
the exact MiniLM model used for LEANN/FAISS; this is **not RAVEL's default BGE
backend**. These encoders use SentenceTransformers' default MPS device on
this Mac. Query inputs are unprefixed; RAVEL keeps native chunk/symbol text,
whereas LEANN/FAISS embed whole fixture files, so document inputs differ. Codanna uses its default MiniLM ONNX provider; grepai uses Ollama's
quantized `all-minilm`; QMD uses its default embeddinggemma GGUF on CPU. Those
provider/model differences prevent attribution of all quality/cost differences
to indexing algorithms. All queries request top 5; RAVEL's evidence budget is
8,192 conservative token units so serialization does not cut off this small
fixture's top 5. RAVEL's full freshness scan stays enabled.

A rerun refuses to replace existing generated fixture directories. Archive them
or choose a new work directory. The freshness script deliberately edits/deletes/
renames only named generated fixture files, after the quality runs finish.

## Timing and memory limits

CLI runs start a fresh process for every query, with warm OS/model caches. API
runs use one process after a warm-up. They are separate cohorts. First-query
measurements for API are included separately. These are not cold-disk measurements.
Some captured runs overlapped development/model work; CPU/GPU isolation was not
established. GPU utilization and actual downstream coding-task outcomes were
not measured. Do not use the snapshots as a claim of universal speed superiority.

`/usr/bin/time -l` records per-CLI peak RSS and CPU time. grepai's separately
running Ollama server is **outside** its CLI RSS. API RSS observations differ:
LEANN/FAISS script samples the parent and descendants every 20 ms, and the
sequential script retains the preparatory MiniLM/FAISS model while measuring
LEANN. RAVEL records its process high-water RSS. These memory observations are
not comparable whole-system peaks. Index bytes include stored metadata/text;
model files and runtime dependencies are reported separately. SQLite free pages
and per-file allocation overhead vary; these are logical file bytes.

QMD `vsearch` in this pinned version invokes generative query expansion. The
measured vector adapter uses `query 'vec: ...' --no-rerank`, which avoids expansion
and reranking. An exploratory `vsearch` download (1.28 GB query-expansion model)
is recorded separately as unused by the final vector adapter. Full QMD default
hybrid generation/reranking was not benchmarked. LEANN uses compact HNSW, not its
incremental IVF backend. Codanna indexes Python symbols only here; the other
systems include both code and Markdown, so they have different supported corpus
sizes. Every topic has a relevant Python function, allowing the same hit metric;
full two-file recall is intentionally not compared.

See [the comparison](../../docs/comparison.md) and [raw environment metadata](environment.json).
