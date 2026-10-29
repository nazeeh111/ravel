# The ravel workspace

Run `ravel inspect --root /path/to/repository` and open the loopback URL printed in
the terminal. The interface is served by the local ravel process. No CDN, web
framework, remote font, analytics or external UI asset is required.

## Search, then read

A single command bar accepts questions, filenames, quoted phrases and exact
symbols. Choose Adaptive, Lexical, Hybrid or Semantic. Adaptive selects from the
retrieval strategies available in the actual index. Semantic strategies require
an explicitly enabled local model; unavailable models produce a visible error.

Context settings live beside the strategy controls. They set the evidence budget
and maximum passages. Budget units are serialized UTF-8 bytes, a conservative
token upper bound, rather than exact tokenizer counts. Source references count
toward that budget; response metadata is separate.

Results form a selectable source list beside a line-numbered reader with local
syntax coloring. Source text is inserted as text nodes, never executable markup.
The Provenance tab shows each passage's actual SHA-256, revision, original or
extracted-text line basis, lexical rank, cosine score and observed calls.
Observed calls are syntax in the displayed source, not resolved dependencies.

Copy one passage or the delivered context selection. Clipboard failure is shown
explicitly, and source text remains selectable. Search failures retain previous
results with a visible error. Empty searches offer concrete recovery suggestions.
Pending searches show progress without invented time estimates.

## Find your way around

- **⌘ / Ctrl K** focuses search.
- **Enter** submits a query.
- **Up / Down** on a source result selects the previous or next passage.
- **Escape** closes context settings or the keyboard-shortcut dialog.
- **Index overview** shows real source counts, vector quota/use, SQLite and model
  storage, source directory and revision. Refresh reads the current index status.
- **Appearance** switches light/dark for this tab.

Recent queries and appearance preferences exist in this tab's memory only.
Reloading clears them. On narrow screens, the source list scrolls horizontally
above the reader and navigation remains available at the top. Reduced motion is
respected. All controls support visible keyboard focus.

## API and implementation

The UI is one packaged HTML file, `src/ravel/inspector.html`, using the existing
same-origin endpoints:

- `GET /api/stats`: actual source counts, index/vector/model bytes, configured
  quota, embedding backend, root and revision.
- `POST /api/search`: `{query, token_budget, mode, limit}`; returns source results,
  planner decisions, freshness and retrieval metrics.

The server binds loopback and validates Host and Origin. The UI introduces no
filesystem or source-editing endpoint. Search can reconcile the index and fill a
local vector cache; source files are not modified.
