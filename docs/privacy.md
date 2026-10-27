# Local data and privacy

The core has no network client, accounts or analytics. Local search uses SQLite
and the approved root only. Optional model acquisition is the sole built-in
network operation and requires `--download-model`. Index text never goes to a
hosted model. There is no hosted-model integration in v0.1.0.

Before loading optional embeddings, RAVEL disables Hugging Face telemetry and
implicit authentication, sets an index-local Hugging Face home and enables
`ORT_DISABLE_TELEMETRY=1` before importing ONNX Runtime. It also calls
`onnxruntime.disable_telemetry_events()` before session creation. Downloads pass
`token=False` explicitly and pin the public model snapshot, avoiding implicit
credential lookups even if an API host imported Hugging Face earlier. Queries use
`local_files_only=True`. Dependency build behavior can vary; RAVEL does not claim
a packet-captured audit of every third-party binary. An API host which imported a runtime before RAVEL controls that earlier import;
RAVEL cannot retroactively change another library's prior behavior. A fresh CLI
process was checked with the ONNX opt-out active and emitted no device-ID warning.
RAVEL itself collects no telemetry. For a hard network boundary, run ordinary
queries under your operating system's network restrictions after model download.

Discovery honors hierarchical `.gitignore` and `.ravelignore` rules, including
negation within discoverable directories. Ignored parent directories stay pruned
as in Git; tracked files are also excluded if current rules match. Hidden files
and directories, symlinks, dependency/build directories, likely credential names,
private-key blocks, common token patterns, binaries, unreadable files and files
over 2 MiB are skipped. There is no permission-denial fallback. Secret detection
is a best-effort additional filter, not a proof that arbitrary source is safe.
Use `.ravelignore` for private material even if Git tracks it.

Example `.ravelignore`:

```gitignore
customer-data/
internal-notes.md
*.sqlite3
```

The local index contains readable source excerpts and lexical postings. Treat it
as private data, not encrypted storage. New index directories request mode 0700
and database files mode 0600. Existing directory permissions are not silently
changed. Python/SQLite operations use the invoking user's access. RAVEL cannot
revoke old backups or filesystem snapshots. SQLite secure deletion is enabled;
`--compact` can reclaim free pages after removal.

The inspector binds `127.0.0.1`, validates Host and Origin and accepts search only
as JSON. It has no arbitrary-file endpoint or cross-origin access. Do not reverse
proxy it publicly. Source content renders as text and remains untrusted data.
The MCP server fixes one root at launch, exposes search/status only and writes
protocol messages to stdout without query logs. A coding agent still needs its
normal consent and source-instruction safeguards.

To remove an index, stop processes using it and delete only the selected root's
`.ravel` directory. That also removes models downloaded for that index. RAVEL
never deletes source files.
