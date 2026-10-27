# Independent pre-release review

Review date: 2026-10-26. A separate reviewer inspected the implementation and exercised synthetic temporary repositories, without editing the engine or tests. No user source data or credential stores were inspected. This was a bounded correctness and privacy review, not an exhaustive security audit or a substitute for benchmark replication.

## Result

No remaining high-severity defect was found in the final delta reviewed before packaging. The expanded test suite passed **23 tests**, including concurrency and cold-process regressions; `ruff check src tests` passed. These are local observations. Remote CI, fresh-clone installation, release artifacts and browser/video verification are separate release checks.

## Confirmed defects repaired and rechecked

| Original finding | Final behavior and evidence |
| --- | --- |
| `index --root` silently indexed the current directory | The approved root is honored; a subprocess test verifies no index appears in an unrelated current directory. |
| Concurrent refresh mixed old text with a new digest | Search holds a single immediate SQLite transaction. A concurrent-writer test verifies coherent old text/hash, followed by the new source on the next search. |
| Concurrent materialization admitted old embeddings for replacement chunks | Materialization now shares the transaction boundary and has no intermediate commits. A pausing-embedder test verifies writers wait and refreshed chunks lose old vectors. |
| Malformed PDF/DOCX aborted other sources | Known parser failures skip the affected document. Healthy source and a valid DOCX remain searchable, with extracted-text line provenance. |
| PDF parser warnings exposed header bytes | Scoped library logging suppression was checked in a fresh subprocess, including the first PDF parser invocation. No source bytes were printed. |
| Lowered vector quota was not enforced or persisted | Reopening with a zero quota immediately removes vector payloads. Ordinary subsequent opens retain the saved quota; lexical searches do not bypass it. |
| Repeated words disappeared from exact phrases | Quoted phrases preserve token order and multiplicity; an absent repeated phrase no longer matches. |
| Non-finite API budgets reached the planner | NaN and infinity are rejected by both transport validation and planner validation. |
| Sliced evidence inherited calls outside its span | Observed calls are attached to their actual source lines and recomputed after context truncation. |

## Local model privacy check

The ordinary local model load and embedding path succeeded with Python socket connection functions and implicit Hugging Face token getters replaced by functions that fail if invoked. This check also imported Hugging Face before RAVEL, exercising the Python-host import-order case. The emitted vector was 388 bytes: 384 int8 components plus a four-byte norm. Explicit public model acquisition uses a pinned revision and `token=False`; ordinary loading sets `local_files_only=True` and supplies the resolved model directory to FastEmbed.

ONNX telemetry is disabled before import through `ORT_DISABLE_TELEMETRY=1`, with the runtime disable call retained. A separate fresh import of the installed ONNX Runtime 1.31.1 completed without the earlier device-ID initialization warning. The upstream [telemetry environment implementation](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/core/platform/telemetry_environment.h) and [initialization path](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/core/platform/telemetry_1ds.cc) document the POSIX environment opt-out. This is targeted execution and source evidence, not a packet-capture audit of arbitrary embedding runtimes.

## Material limits

- Freshness means the source snapshot read during the current scan. A file can change after that scan; the evidence hash identifies the bytes actually indexed. Concurrent database updates are serialized to avoid mixing generations.
- Latency and candidate-memory settings are planning allowances. Full source hashing, parser/model startup, process memory and SQLite overhead are not hard real-time or process-RSS guarantees.
- Hybrid mode reranks lexical candidates. Cold semantic work may cover only part of the corpus; semantic coverage is returned explicitly. Benchmark results must preserve these limits.
- PDF/DOCX locations refer to extracted text lines, not native page coordinates. Python call observations are syntax, not verified cross-file dependency resolution.
- Scoped PDF logging changes the `pypdf` parent logger temporarily. The parser is not an isolation sandbox for hostile documents or arbitrary application logging customizations.

## Supplemental UTF-8 portability review

A focused delta review checked explicit UTF-8 fixture writes and standard-stream configuration in the CLI and direct MCP entry point. The new subprocess regression sets `PYTHONIOENCODING=cp1252`, retrieves Chinese source text through CLI JSON output, then sends a UTF-8 Chinese query through MCP and checks the returned source text. The focused test passed locally (`1 passed, 19 deselected`); lint passed for the changed CLI, server and test files. No issue requiring a change was found in this delta.

This is legacy-code-page emulation on macOS. It does not establish that the patched revision has passed remote Windows CI. The earlier 23-test result above describes the preceding reviewed source; this supplemental check does not claim a new complete-suite or remote-CI result. Core retrieval behavior and benchmark measurements were outside this focused delta.
