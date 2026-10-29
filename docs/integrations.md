# Codex and Claude Code

Install ravel first. Use an absolute executable path when a client does not inherit
your shell PATH. Each server is restricted to the source root you name.

```sh
ravel index /absolute/path/to/repository
codex mcp add ravel -- ravel mcp --root /absolute/path/to/repository
claude mcp add --transport stdio ravel -- ravel mcp --root /absolute/path/to/repository
```

These commands follow the official [Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
and [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp).
They are configuration examples, not a claim that an end-to-end coding session
was run inside either proprietary client.

Equivalent Codex TOML:

```toml
[mcp_servers.ravel]
command = "/absolute/path/to/ravel"
args = ["mcp", "--root", "/absolute/path/to/repository"]
```

Equivalent project `.mcp.json` for Claude Code:

```json
{
  "mcpServers": {
    "ravel": {
      "type": "stdio",
      "command": "ravel",
      "args": ["mcp", "--root", "/absolute/path/to/repository"]
    }
  }
}
```

Check the server in the client's MCP list. Ask: “Use ravel_search to find the
function that retries failed operations. Return evidence within 2048 budget units.”
The tools are `ravel_search(query, token_budget, limit, mode, latency_ms, memory_kib)`
and `ravel_status()`. They expose no source modification, network or arbitrary-root
parameter. Search refreshes its index automatically; normal filesystem policy
still applies. Context units conservatively count evidence bytes, not exact
client tokens. Model protocol overhead is outside that allowance.

ravel implements the standard newline-delimited JSON-RPC stdio transport and
initialize, notifications, ping, tools/list and tools/call. Automated tests check
actual subprocess wire messages, schemas, successful retrieval and invalid tool
arguments. Protocol versions 2024-11-05, 2025-03-26, 2025-06-18 and 2025-11-25 are
negotiated; unknown clients are offered 2025-06-18. No SDK is required at runtime.

## Python

```python
from ravel import Index

with Index("/absolute/path/to/repository") as index:
    index.sync()
    answer = index.search("retry_with_backoff", token_budget=2048)
    for hit in answer["results"]:
        print(hit["path"], hit["start_line"], hit["end_line"], hit["text"])
```

Only explicit `enable_semantic(download=True)` permits a model download.
`enable_semantic()` reuses local model files. `cache_bytes` bounds persisted vector
payload bytes; model and SQLite overhead are reported separately.

## Verification recorded for v0.1.0

The real official MCP Python client completed initialize, tools/list and tools/call
against the ravel subprocess, negotiated protocol `2025-11-25`, and retrieved
`retry.py` / `retry_with_backoff` within the requested evidence budget. Reproduce:

```sh
uv run --with mcp --python .venv/bin/python scripts/verify_mcp.py
```

The installed Codex CLI also parsed ravel's stdio command and fixed-root arguments
using transient `-c` configuration overrides and reported the server enabled. This
check did not modify the user's persistent configuration or run a downstream
coding task. No Claude Code executable was installed on the verification host, so
its configuration remains documentation-checked plus shared-protocol tested.
