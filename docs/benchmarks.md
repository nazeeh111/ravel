# Experiments and honest limits

RAVEL's adaptive policy is an engineering experiment. The measurements here support bounded local retrieval tradeoffs, not universal superiority or better patch-generation success. The [separate comparison](comparison.md) executes LEANN, QMD, Codanna, grepai and FAISS. Those runs use a different fixture and include explicitly disclosed model/interface differences.

## Independent small suite

The evaluator was written separately from the retrieval implementation. It contains **48 developer-authored queries** over **36 files and 6,521 source bytes**: 24 training queries and 24 held-out queries. Training and evaluation cover disjoint source subjects, with exact-name and natural-intent questions for Python functions and ordinary Markdown documents. Gold paths were fixed before measurement. The extra off-topic documents are easy distractors. This is a small regression/ablation suite, not a public benchmark or evidence of production-scale generalization.

[Queries](../benchmarks/queries.json), [reproduction script](../benchmarks/evaluate.py), [machine-readable summary](../benchmarks/results/summary.json) and all per-query outputs are included. The summary records core source SHA256 values; raw runs record the implementation bytes they measured. Source changes after measurement must not silently inherit these numbers.

All internal semantic configurations use the same local **BAAI/bge-small-en-v1.5** fastembed model and symmetric int8 document vectors. The quantized ONNX weights are pinned to `qdrant/bge-small-en-v1.5-onnx-q` revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`. There are no model API calls. The model cache is shared across experiment processes, and downloaded model storage is reported separately from each SQLite index. SQLite size includes its source text, metadata, FTS postings and cached vector payload. `cache_bytes` is a vector-payload quota; it does not bound total SQLite, model or process memory.

Each configuration runs in a separate process with its own SQLite database. Exact queries use a 1,200-unit context budget, intent queries 4,096; the soft latency target is 1,000 ms and candidate-memory setting 2,048 KiB. Each query is run three times. “First” means the first repetition of that query in a process that may already have run earlier queries; it is **not an operating-system cold-cache measurement**. “Warm” combines the second and third repetitions. Model load plus initial lexical indexing and optional vector materialization are timed separately. Lexical-only does not load an embedding model.

The host also ran development/other benchmark work during parts of measurement. Latency and CPU samples are observed snapshots with interference, not isolated hardware performance estimates. `process_peak_rss_bytes` is that configuration's whole-process peak resident memory, including the model when loaded. CPU seconds include setup and all its queries. GPU utilization was not sampled; this internal pipeline uses CPU inference.

<!-- RESULTS_START -->
| Configuration | MRR | Recall ≤8 | First p50/p95 ms | Warm p50/p95 ms | SQLite KiB | Vector bytes | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical only | 0.6865 | 0.7917 | 24.3 / 30.9 | 24.6 / 33.6 | 76 | 0 | 29.7 |
| Fixed hybrid, full cache | 0.7812 | 0.8750 | 48.8 / 95.5 | 46.9 / 106.6 | 92 | 13,968 | 222.1 |
| Semantic, full cache | 0.9375 | 1.0000 | 58.5 / 91.9 | 58.2 / 104.8 | 92 | 13,968 | 218.2 |
| Heuristic, full cache | 0.9375 | 1.0000 | 89.9 / 124.2 | 89.4 / 140.0 | 92 | 13,968 | 224.8 |
| Heuristic, 4-vector quota | 0.7708 | 0.7917 | 272.2 / 1148.2 | 157.5 / 1147.7 | 76 | 1,552 | 229.2 |
| Heuristic, no retained vectors | 0.7812 | 0.8750 | 376.5 / 1172.2 | 399.7 / 1126.9 | 76 | 0 | 214.2 |
| Learned, full cache | 0.9375 | 1.0000 | 61.8 / 81.8 | 62.5 / 81.4 | 92 | 13,968 | 222.0 |

Measured on macOS 26.6.2 / arm64, Python 3.12.13, 10 logical CPUs. Model cache: **67,218,141 unique file bytes** (64.1 MiB), excluding symlink aliases; allocated file bytes 67,252,224. The naive per-path logical sum is 200,862,428 bytes and overcounts Hugging Face shared-blob aliases.

The source corpus is smaller than every database in this tiny experiment: fixed SQLite metadata dominates. This is not evidence of an index smaller than source. Full int8 vector payload is 13,968 bytes (36 × 388); the corresponding 384-dimensional float32 payload alone would be 55,296 bytes, before any metadata. This arithmetic is not a measured float32 retrieval-quality ablation.

The full-cache heuristic and learned selector tie on held-out quality. Their timings were collected at different points in a shared machine workload, so the apparent latency difference does not establish a reliable policy advantage. The small-cache and no-cache configurations are smaller on disk but suffer lower recall and repeated compute. On this suite their first repetitions exceeded the 1-second target on five of 24 held-out queries each.

Startup plus lexical indexing ranged from 42.0 to 1872.2 ms across these processes. Full-cache materialization ranged from 598.0 to 1418.1 ms and is paid before the reported queries. Raw JSON retains each process CPU total, cache hits/misses, precision, context byte cost, coverage and setup costs.
<!-- RESULTS_END -->

MRR is the mean reciprocal rank of the first gold file, after deduplicating retrieved paths. Recall is the fraction of gold paths returned, and precision uses the number of unique returned files. For the small suite the engine returns at most eight evidence items; delivered context packing can reduce that number. Rankings are scored from actual delivered evidence, not a hidden unbudgeted ranking.

The context cost is the serialized result's **UTF-8 byte count**, a conservative upper bound for byte-fallback tokenizers. It includes paths, line ranges, hashes and evidence metadata. It is deliberately more restrictive than usual English token estimates and is **not** an exact Codex/Claude tokenizer count. Planner/metrics envelope bytes are outside the evidence budget.

## Heuristic versus lightweight learned selection

The optional learned policy is a real small softmax linear classifier, with six bounded features and three actions: lexical, hybrid and semantic. It learns only from the 24 training queries. No embedding model was trained. The six inputs are identifier shape, query length, top lexical coverage, cached-vector coverage, latency target and context budget.

Training labels select the action with greatest measured utility:

```text
reciprocal_rank
- 0.05 * min(median_latency_ms / 1000, 2)
- 0.02 * context_byte_upper_bound / context_budget
```

[Training-label evidence](../benchmarks/results/training-labels.json) includes each measured action and utility. The [learned weights](../benchmarks/results/learned-policy.json) contain no source text or queries. Cache coverage is set to the fully populated-cache feature value used for this comparison. The classifier is tested on the disjoint subject set, with the same full-cache setup as the heuristic. This tiny training set and timing-sensitive labels are not a validated general-purpose policy; the deterministic heuristic remains the default. The final held-out run ties quality; timing interference prevents a reliable policy-latency conclusion. Neither selector is an oracle.

The cache ablation compares full pre-materialization, a four-vector payload quota (1,552 bytes), and no retained vectors. Full-cache runs pay materialization time explicitly. Cold constrained-cache runs compute selected vectors as needed, then evict by observed use and regeneration cost per byte. A small cache can increase recomputation, change the estimated affordable retrieval strategy, reduce recall, or exceed the soft latency target. The smaller database is not automatically faster. No-cache and four-vector results are workload-dependent, rather than an isolated proof that the eviction formula is optimal.

A separate [budget sweep](../benchmarks/results/budget-sweep.json) uses four predeclared held-out intent queries with a warm full-vector cache. It varies the soft latency target (25/200/1,000 ms), candidate-memory setting (64/2,048 KiB), and context budget (1,200/4,096 byte upper-bound units). Candidate-memory settings constrain retrieval depth; they are not guarantees about process RSS or SQLite/model internals.

## Freshness

The experiment verifies addition, edit, rename and deletion through the normal refresh-before-search API. It checks the new symbol appears, removed symbol/source text disappears, and renamed evidence cites the new path. Broad lexical search can still return other current files sharing query words; that is not stale evidence. Timings and individual pass/fail observations are in the summary's `freshness` object. The product's tests additionally cover permissions, exclusions, branch/revision behavior, concurrency and model/cache handling; benchmark observations do not substitute for those tests.

## One official ContextBench task, used as a diagnostic

A bounded public-data check uses `SWE-Bench-Verified__python__maintenance__bugfix__90532e38`, the first xarray task in the downloaded ContextBench test file, selected before running retrieval. The source snapshot is [pydata/xarray at 19b088636eb7d3f65ab7a1046ac672e0689371d8](https://github.com/pydata/xarray/tree/19b088636eb7d3f65ab7a1046ac672e0689371d8). Only the original issue text is submitted to search. The patch and annotated context are excluded from the retrieval input. Gold paths are used only for scoring. The downloaded metadata SHA256, original task identifier, query hash, source spans, actual paths and configuration are retained in [raw diagnostic results](../benchmarks/results/contextbench-diagnostic.json).

This is a **static file-retrieval diagnostic on one task**, not the official agent trajectory/line-level ContextBench protocol, a leaderboard score or an end-to-end coding-task evaluation. It indexes eligible text files with ordinary RAVEL exclusions, uses a 32,000-byte upper-bound evidence budget, returns up to 20 items and requests a soft 3-second latency target. It does not train the selector. It does not execute a repair or the upstream project's tests. The archive has no `.git`, so result-level revisions remain null; the report records the independently pinned archive revision without inventing an engine-observed commit.

<!-- OFFICIAL_START -->
| Strategy | First RR / file recall | Next two RR / file recall | First latency | Next two latencies |
| --- | ---: | ---: | ---: | ---: |
| lexical | 0.20 / 1.00 | 0.20 / 1.00; 0.20 / 1.00 | 0.66s | 1.27s; 0.63s |
| hybrid | 0.50 / 1.00 | 0.50 / 1.00; 0.50 / 1.00 | 3.85s | 1.24s; 0.69s |
| auto | 0.50 / 1.00 | 0.50 / 1.00; 0.50 / 1.00 | 3.60s | 0.72s; 1.39s |

The final snapshot indexes **204 eligible files and 5,555 chunks**, with an approximately 10.9 MiB SQLite index. In this final run auto and hybrid deliver both annotated gold paths on all three repetitions, improving their first gold-file rank over lexical. Auto exceeds its soft 3-second target on the first query. Semantic coverage remains below 0.4%: these are lexical-preserving shortlists with selective semantic work, not full semantic scans. Ranking and context packing remain deadline-sensitive. One successful task is not a generalization claim.
<!-- OFFICIAL_END -->

The diagnostic exposed a real weakness missed by the small suite: cold partial semantic sampling could discard useful lexical results and miss every gold file. Auto mode now preserves lexical evidence when cache coverage is low and the corpus exceeds the affordable depth. [Before-fix evidence](../benchmarks/results/contextbench-before-fix.json) is retained. Remaining failures and partial coverage are reported, rather than relabeling them as success. Hybrid mode reranks lexical candidates, so it cannot recover candidates absent from its lexical shortlist. A cold sampled semantic search is not a complete corpus nearest-neighbor search. Materializing the complete vector cache can improve coverage but consumes storage and indexing compute.

Agent Retrieval Bench and CORE-Bench were inspected for relevance definition, candidate sets, frozen revisions, token packing and licensing. Full runs were not completed. No score is claimed for them. ARB's official all-files candidate universe and canonical token packing differ from RAVEL's source-exclusion and byte-budget protocol. CORE-Bench's data are CC-BY-NC-SA-4.0 and are not bundled as MIT data. See [research](research.md) and [attribution](attribution.md).

## Reproduce

From a fresh checkout with Python 3.10+ and a free local-model download permitted:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[semantic]'
.venv/bin/python benchmarks/evaluate.py --work /tmp/ravel-eval-fresh --download-model
.venv/bin/python benchmarks/evaluate.py --work /tmp/ravel-eval-fresh \
  --model-dir /tmp/ravel-eval-fresh/models --budget-sweep
```

Use a fresh work directory. The evaluator preserves previous temporary results and refuses to overwrite a nonempty main work directory. To reuse an existing local model without network, pass `--model-dir /path/to/model-cache` and omit `--download-model`. Saved result JSON is refreshed only when a configuration completes. Optional evaluation-only dependencies for the official diagnostic are `pyarrow`; they are not product runtime dependencies.

```sh
.venv/bin/python -m pip install pyarrow
curl -L --fail \
  https://huggingface.co/datasets/Contextbench/ContextBench/resolve/main/data/test.parquet \
  -o /tmp/contextbench-test.parquet
curl -L --fail \
  https://codeload.github.com/pydata/xarray/tar.gz/19b088636eb7d3f65ab7a1046ac672e0689371d8 \
  -o /tmp/ravel-xarray.tar.gz
mkdir /tmp/ravel-xarray-snapshot
tar -xzf /tmp/ravel-xarray.tar.gz -C /tmp/ravel-xarray-snapshot --strip-components=1
.venv/bin/python benchmarks/evaluate.py --work /tmp/ravel-official-fresh \
  --contextbench-parquet /tmp/contextbench-test.parquet \
  --snapshot /tmp/ravel-xarray-snapshot --model-dir /tmp/ravel-eval-fresh/models
```

The metadata download URL's `main` may change; compare the downloaded SHA256 with the recorded diagnostic before comparing results. The source archive URL pins the exact repository commit. Preserve upstream licenses if redistributing source/corpus bytes. Only derived metrics and provenance are distributed here.
