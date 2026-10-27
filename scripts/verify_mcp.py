"""Optional interoperability check with the official MCP Python client.

Run: uv run --with mcp --python .venv/bin/python scripts/verify_mcp.py
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    sample = Path(__file__).resolve().parents[1] / 'examples' / 'sample'
    params = StdioServerParameters(command=sys.executable, args=['-m', 'ravel', 'mcp', '--root', str(sample)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            listing = await session.list_tools()
            result = await session.call_tool('ravel_search', {'query': 'retry_with_backoff', 'token_budget': 2048})
            payload = json.loads(result.content[0].text)
            error = getattr(result, 'is_error', None)
            if error is None:
                error = result.isError
            assert not error
            assert payload['results'][0]['symbol'] == 'retry_with_backoff'
            print(json.dumps({'protocol': getattr(init, 'protocol_version', None) or getattr(init, 'protocolVersion'),
                              'server': (getattr(init, 'server_info', None) or getattr(init, 'serverInfo')).name,
                              'tools': [t.name for t in listing.tools], 'retrieved': payload['results'][0]['path'],
                              'token_budget_honored': payload['metrics']['tokens_used'] <= 2048}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
