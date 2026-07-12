"""
Sample client for testing the vClinic MCP server.

Stdio transport (spawns the server as a subprocess) — default:
    python sample_client.py

To start the MCP server with a fresh database, set VCLINIC_REINIT=1:
    VCLINIC_REINIT=1 python sample_client.py

Streamable HTTP transport (connects to an already-running server):
    python -m server --transport streamable-http --host 127.0.0.1 --port 8000
    MCP_TRANSPORT=streamable_http MCP_URL=http://127.0.0.1:8000/mcp python sample_client.py

SSE transport (connects to an already-running server):
    python -m server --transport sse --host 127.0.0.1 --port 8000
    MCP_TRANSPORT=sse MCP_URL=http://127.0.0.1:8000/sse python sample_client.py
"""
import os
import sys
import asyncio
from pathlib import Path
from langchain_mcp_adapters.client import MultiServerMCPClient

_PROJECT_ROOT = Path(__file__).parent

def _stdio_server_config(reinit: bool = False) -> dict:
    """Stdio MCP server config for langchain-mcp-adapters.

    Pass reinit=True (or set VCLINIC_REINIT=1) to wipe and recreate the DB.
    """
    args = ["-m", "server"]
    if reinit:
        args.append("--reinit")
    return {
        "vclinic": {
            "command": "python",
            "args": args,
            "transport": "stdio",
            "env": {**os.environ, "PYTHONPATH": str(_PROJECT_ROOT)},
        }
    }


def _streamable_http_server_config(url: str) -> dict:
    """Streamable HTTP MCP server config for langchain-mcp-adapters.

    Assumes the server is already running (e.g. via
    `python -m server --transport streamable-http`) and reachable at `url`.
    """
    return {
        "vclinic": {
            "url": url,
            "transport": "streamable_http",
        }
    }


def _sse_server_config(url: str) -> dict:
    """SSE MCP server config for langchain-mcp-adapters.

    Assumes the server is already running (e.g. via
    `python -m server --transport sse`) and reachable at `url`.
    """
    return {
        "vclinic": {
            "url": url,
            "transport": "sse",
        }
    }


def _mcp_server_config(reinit: bool = False) -> dict:
    """Build the MCP server config based on MCP_TRANSPORT (default: stdio)."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip()
    if transport in {"streamable_http", "streamable-http", "http"}:
        url = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
        return _streamable_http_server_config(url)
    if transport == "sse":
        url = os.environ.get("MCP_URL", "http://127.0.0.1:8000/sse")
        return _sse_server_config(url)
    return _stdio_server_config(reinit=reinit)

if __name__ == "__main__":
    async def main():
        reinit = os.environ.get("VCLINIC_REINIT", "").strip() == "1"
        mcp_client = MultiServerMCPClient(_mcp_server_config(reinit=reinit))
        all_tools = await mcp_client.get_tools()

        print(f"Total tools registered: {len(all_tools)}")
        for tool in all_tools:
            print(f"Tool: {tool.name}")
            print(f"Description: {tool.description}")
            print(f"Input schema: {tool.input_schema}")
            print("-" * 40)
    
    asyncio.run(main())
