# Index inspector

The inspector is a small local interface for querying a real RAVEL index. It shows source passages, line ranges, the selected retrieval strategy, elapsed query time, the conservative token upper bound and storage use. It contains no analytics, external scripts, fonts, or remote assets.

Start it with `ravel inspect` from your indexed directory. Open the loopback URL printed in the terminal. The CLI and server remain the authority for supported arguments; use `ravel inspect --help` for configuration.

Use **Adaptive** to let the planner select a retrieval route. Choose **Lexical**, **Hybrid** or **Semantic** for a direct comparison on the same query. Set a context budget and result limit before searching. Budget units are serialized UTF-8 bytes, a conservative upper bound for byte-fallback tokenizers, rather than an exact tokenizer count. The bound covers evidence and its provenance; protocol overhead is separate. An unavailable embedding backend is reported by the server rather than replaced by simulated results. Copy context to move the displayed source passages into an editor.

The query list lives only in the current tab's JavaScript memory. Reloading clears it. Clipboard access may require browser permission. Paths and source text are rendered as text, including any markup inside indexed files. No results or performance values are hardcoded.

## Interface contract

The single HTML file is `src/ravel/inspector.html`. It expects same-origin JSON endpoints:

- `GET /api/stats`: `files`, `chunks`, `index_bytes`, `cache_bytes`, `embedding_backend`, `root`, `revision`.
- `POST /api/search`: request `{query, token_budget, mode, limit}`; response `{results, plan, metrics}`.
- Result fields: `path`, `start_line`, `end_line`, `text`, `symbol`, `score`, `evidence`, `revision`.
- Plan fields: `strategy`, `reason`. Metrics: `elapsed_ms`, `tokens_used`, optional `freshness`.

The server should bind to loopback and reject cross-origin requests. The browser sends only same-origin requests. The inspector is read-only with respect to source files, but searches may refresh an index or populate an embedding cache according to the engine's configured policy.

## Visual identity

RAVEL's mark uses four interwoven teal paths that converge on a single copper point. Warm paper and dark ink keep long source passages comfortable to read. The identity is original SVG, editable without a design application. The inspector uses system fonts and exposes source evidence before supporting metrics. It adapts to narrow screens and honors reduced-motion preferences.
