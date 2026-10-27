# Measured comparisons and their limits

RAVEL retrieves all 32 top-ranked answers in this small, model-matched MiniLM
smoke test. So do compact LEANN and exact FAISS. **LEANN and FAISS use less index
storage here.** Compressed vector payloads do not automatically produce the
smallest complete index: RAVEL's SQLite schema, full-text index, symbols and
provenance have fixed costs.

These executed comparisons used one Apple M4 / 32 GiB Mac on 2026-10-26. They
establish that the systems ran on a common fixture. They are not a large-scale
leaderboard, isolated hardware experiment, or proof of general superiority.
[Raw runs and reproducible adapters](../benchmarks/external/README.md) include
query paths, errors, configuration and calculations. Separate
[planner experiments](benchmarks.md) evaluate RAVEL's adaptive contribution.

## Shared corpus and retrieval quality

The fixture has 16 hand-written topics, each represented by one Python function
and one Markdown document: **32 files / 5,869 bytes**, 16 natural-language
questions and 16 exact symbol queries. Functions are retrieval fixtures, not
implementations of the described algorithms. Either corresponding file counts
as relevant. Hit@1 is the fraction whose first file is relevant. MRR@5 averages
the reciprocal rank of the first relevant result in the first five. All adapters
request top 5; these file-level metrics do not measure answer generation.

| System and actual mode | Natural hit@1 | Identifier hit@1 | Overall hit@1 | Complete index bytes |
| --- | ---: | ---: | ---: | ---: |
| RAVEL, model-free lexical CLI | 13/16 | 16/16 | 29/32 | 86,016 |
| RAVEL, auto + matched MiniLM/int8 API | 16/16 | 16/16 | 32/32 | 94,208 |
| RAVEL, semantic + matched MiniLM/int8 API | 16/16 | 16/16 | 32/32 | 94,208 |
| LEANN 0.3.8, compact HNSW / MiniLM API | 16/16 | 16/16 | 32/32 | **55,043** |
| FAISS 1.15.1, exact float32 / MiniLM API | 16/16 | 16/16 | 32/32 | **56,444** |
| Codanna 0.17.1, MiniLM semantic CLI | 16/16 | 16/16 | 32/32 | 89,988 |
| grepai 1.1.0, Ollama all-minilm semantic CLI | 16/16 | 16/16 | 32/32 | 104,310 |
| QMD 2.8.3, BM25 CLI | 0/16 | 16/16 | 16/32 | 208,896 |
| QMD 2.8.3, embeddinggemma structured vector CLI | 16/16 | 16/16 | 32/32 | 3,399,680 |

Index bytes include metadata/text and caches; models and runtime dependencies
are separate. FAISS includes an explicit passage/filename metadata file but
omits RAVEL's freshness scanner, AST symbols and full provenance schema. SQLite
page allocation matters at this scale. Codanna indexes the 16 Python files;
other tools index both file types. Full two-file recall is not compared.

This suite's quality ceiling is easy to reach. A larger corpus could reverse
any ordering. QMD's BM25 result reflects conjunction of complete natural queries;
keyword rewriting or its richer hybrid pipeline could improve that result.

RAVEL's matched runs inject `sentence-transformers/all-MiniLM-L6-v2` with the
same unprefixed query inputs as LEANN and FAISS, storing int8 vectors.
RAVEL retains its native chunking and symbol prefix; LEANN/FAISS receive whole
fixture files, so the document representations are not byte-identical.
This is an experimental API configuration, **not RAVEL's default BGE backend**.
Codanna uses MiniLM ONNX; grepai uses Ollama's quantized all-minilm; QMD uses
embeddinggemma GGUF. Their numerical representations/providers differ. Codanna's
threshold is 0 rather than its default 0.6, obtaining unfiltered top 5. RAVEL's
budget is 8,192 conservative token units and freshness scanning stays enabled.
Its semantic latency target is relaxed to 60 seconds so budget sampling does not
confound ranking on this small fixture.

## Latency snapshots, separated by invocation method

These measurements have warm OS/model caches. Some runs overlapped other
development/model work. Process startup, provider and model loading dominate
some rows. GPU utilization, thermal state, cold-disk behavior and isolated
scheduling were not measured. **Do not compare API rows directly against CLI
rows or use these snapshots as a universal speed claim.**

| Warm in-process API, same MiniLM model, one warm-up | p50 ms | p95 ms |
| --- | ---: | ---: |
| Exact FAISS | **81.18** | 920.12 |
| RAVEL auto, freshness scan included | 94.96 | **116.24** |
| RAVEL semantic, freshness scan included | 112.55 | 214.93 |
| LEANN compact HNSW | 280.54 | 4,517.11 |

| Fresh CLI process per query, warm OS/model cache | p50 ms | p95 ms |
| --- | ---: | ---: |
| grepai + separate local Ollama server | **72.91** | **194.76** |
| RAVEL lexical, freshness scan included | 301.33 | 513.22 |
| QMD BM25 | 564.41 | 1,062.35 |
| Codanna semantic | 637.44 | 984.56 |
| QMD structured vector, CPU only | 4,614.70 | 28,404.36 |

Nearest-rank p95 over just 32 queries is noisy. FAISS's lower observed median
and grepai's responsive local-server workflow are practical competitor strengths.
Persistent MCP sessions can avoid CLI startup; warm MCP throughput is unmeasured.

QMD uses documented `query 'vec: ...' --no-rerank`, avoiding generation and
reranking. This pinned version's `vsearch` invokes generative expansion despite
its brief help saying vector-only. An exploratory expansion sweep was stopped
and excluded. Full QMD default hybrid expansion/reranking was not benchmarked.

## Indexing, models and explicit incremental updates

Observed indexing snapshots: RAVEL lexical API scanning took 0.110 seconds plus
1.934 seconds to materialize matched vectors; FAISS vector/metadata construction
took 3.598 seconds; LEANN compact HNSW took 33.241 seconds. Their model was
prepared outside these timers. CLI indexing took 0.380 seconds for RAVEL lexical,
0.564 seconds for QMD lexical, 1.859 seconds for Codanna and 0.421 seconds for
grepai. CLI timings include initialization/cache setup; preparation conditions
are not identical. QMD's final vector report records an **unchanged embedding
pass**, not a valid initial semantic indexing time. No semantic indexing speed
claim is made for that row.

| Local model files, separately from indexes | Logical bytes |
| --- | ---: |
| LEANN/FAISS/RAVEL matched MiniLM download | 91,578,455 |
| Codanna MiniLM ONNX cache | 91,102,076 |
| grepai Ollama all-minilm | 45,960,996 |
| QMD embeddinggemma GGUF | 333,590,944 |
| Unused exploratory QMD expansion model | 1,282,438,912 |

The final QMD vector adapter does not need the exploratory expansion model.
Runtime dependencies are excluded; pinned external Python requirements and
binary hashes are retained. Default RAVEL BGE overhead is reported separately.

After quality measurements, the update test changed `retry.py` to a new
function, deleted `retry.md`, and renamed `lease.py` to `lease_renamed.py`.
Explicit updates for **QMD lexical, Codanna and grepai all returned new/renamed
paths and omitted deleted/old paths**. Observed update command times were 466 ms,
3,603 ms and 790 ms. This verifies explicit refresh, not unrefreshed-query
behavior. [Raw checks](../benchmarks/external/freshness.json) are included.
LEANN's incremental IVF backend was not exercised by this compact-HNSW adapter.
RAVEL's own tests cover freshness, branches, exclusions and privacy. Competitors
already have incremental features; RAVEL does not claim them as novel.

Per-CLI raw records contain CPU time and peak process RSS. grepai's RSS excludes
its separate Ollama server. API memory methods differ; LEANN's run retains the
preparatory MiniLM/FAISS model. They are **not comparable whole-system peaks**;
no memory-superiority claim is made. ContextBench coverage is a limited official
task smoke test in the separate planner report. Agent Retrieval Bench,
large-scale ContextBench and reproducible downstream coding-agent outcomes
remain unmeasured. These are explicit alpha-release limits.
