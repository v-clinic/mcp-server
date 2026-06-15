"""
Sample client for testing the vClinic MCP server.
Run from the project root with:
    python sample_client.py

To start the MCP server with a fresh database, set VCLINIC_REINIT=1:
    VCLINIC_REINIT=1 python sample_client.py
"""
import os
import sys
import asyncio
from pathlib import Path
from langchain_mcp_adapters.client import MultiServerMCPClient

_PROJECT_ROOT = Path(__file__).parent

def _mcp_server_config(reinit: bool = False) -> dict:
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
