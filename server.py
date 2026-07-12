"""
vClinic MCP Server — entry point.

Run from the project root with:
    python -m server

Pass --reinit to wipe and recreate the database (drops all data):
    python -m server --reinit

By default the server speaks MCP over stdio. To serve over a network
transport instead (e.g. for a network-accessible deployment), pass
--transport with either "sse" or "streamable-http":
    python -m server --transport streamable-http --host 127.0.0.1 --port 8000
    python -m server --transport sse --host 127.0.0.1 --port 8000

Transport, host, and port can also be set via environment variables
(useful when the CLI args aren't easily controlled, e.g. container startup):
    MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8000 python -m server
    MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8000 python -m server
CLI arguments take precedence over environment variables.

Or configure in VS Code / Claude Desktop as:
    {
        "command": "python",
        "args": ["-m", "server"],
        "cwd": "<path-to-vClinic>"
    }
"""

from mcp.server.fastmcp import FastMCP

from backend.db import init_db
from tools.seed_stuff import (
    seed_staff,
)
from tools.patient_tools import (
    create_patient,
    get_patient,
    search_patients,
)
from tools.visit_tools import (
    create_visit,
    get_visit,
    get_visits_for_patient,
    update_visit,
)
from tools.diagnosis_tools import (
    create_diagnosis,
    update_diagnosis,
    get_diagnoses_for_visit,
)
from tools.treatment_tools import (
    create_treatment,
    update_treatment,
    get_treatments_for_visit,
)
from tools.lab_tools import (
    create_lab_order,
    get_lab_order,
    get_pending_lab_orders,
    update_lab_order_status,
    create_lab_result,
    get_lab_results,
    update_lab_result,
)
from tools.radiology_tools import (
    create_radiology_order,
    get_radiology_order,
    get_pending_radiology_orders,
    update_radiology_order_status,
    create_radiology_report,
    get_radiology_report,
    update_radiology_report,
)
from tools.medical_search_tools import (
    search_pubmed,
    get_clinical_guidelines,
)
from rag_tools.rag_tools import init_rag_collection, search_clinic_knowledge
from cache.manager import get_cache_manager

# ---------------------------------------------------------------------------
# CLI / environment configuration
# ---------------------------------------------------------------------------
import argparse
import os
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vClinic MCP server")
    parser.add_argument("--reinit", action="store_true",
                         help="Wipe and recreate the database on startup.")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"],
                         default=os.environ.get("MCP_TRANSPORT", "stdio"),
                         help="MCP transport to serve. Default: stdio.")
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"),
                         help="Host to bind when using sse/streamable-http. Default: 127.0.0.1.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8000")),
                         help="Port to bind when using sse/streamable-http. Default: 8000.")
    return parser.parse_args()


_args = _parse_args()

# ---------------------------------------------------------------------------
# Initialise DB (creates tables + seeds default staff on first run)
# Pass --reinit on the command line to wipe and recreate the database.
# ---------------------------------------------------------------------------
_db_path = Path(__file__).parent / "data" / "vclinic.db"
if _args.reinit and _db_path.exists():
    _db_path.unlink()
if _args.reinit or not _db_path.exists():
    init_db()

# ---------------------------------------------------------------------------
# Initialise RAG collection (build or load ChromaDB index at startup)
# ---------------------------------------------------------------------------
init_rag_collection()

# ---------------------------------------------------------------------------
# FastMCP server
# host/port only take effect for network transports (sse, streamable-http);
# they are ignored by FastMCP when running over stdio.
# ---------------------------------------------------------------------------
mcp = FastMCP("vclinic-mcp-server", host=_args.host, port=_args.port)

from audit_logger import audit
# staff tools
mcp.tool()(audit(seed_staff))

# Patient tools
mcp.tool()(audit(create_patient))
mcp.tool()(audit(get_patient))
mcp.tool()(audit(search_patients))

# Visit tools
mcp.tool()(audit(create_visit))
mcp.tool()(audit(get_visit))
mcp.tool()(audit(get_visits_for_patient))
mcp.tool()(audit(update_visit))

# Diagnosis tools
mcp.tool()(audit(create_diagnosis))
mcp.tool()(audit(update_diagnosis))
mcp.tool()(audit(get_diagnoses_for_visit))

# Treatment tools
mcp.tool()(audit(create_treatment))
mcp.tool()(audit(update_treatment))
mcp.tool()(audit(get_treatments_for_visit))

# Lab tools
mcp.tool()(audit(create_lab_order))
mcp.tool()(audit(get_lab_order))
mcp.tool()(audit(get_pending_lab_orders))
mcp.tool()(audit(update_lab_order_status))
mcp.tool()(audit(create_lab_result))
mcp.tool()(audit(get_lab_results))
mcp.tool()(audit(update_lab_result))

# Radiology tools
mcp.tool()(audit(create_radiology_order))
mcp.tool()(audit(get_radiology_order))
mcp.tool()(audit(get_pending_radiology_orders))
mcp.tool()(audit(update_radiology_order_status))
mcp.tool()(audit(create_radiology_report))
mcp.tool()(audit(get_radiology_report))
mcp.tool()(audit(update_radiology_report))

# Medical knowledge search tools
mcp.tool()(audit(search_pubmed))
mcp.tool()(audit(get_clinical_guidelines))
mcp.tool()(audit(search_clinic_knowledge))


def get_cache_stats() -> dict:
    """Return per-namespace cache hit/miss counts, hit rate, size, and TTL.

    Useful for verifying cache effectiveness and diagnosing staleness issues.
    Contains no patient data — only counters and configuration.
    """
    return get_cache_manager().stats()


mcp.tool()(audit(get_cache_stats))


if __name__ == "__main__":
    if _args.transport == "streamable-http":
        print(f"[vClinic MCP] Serving Streamable HTTP on http://{_args.host}:{_args.port}/mcp", flush=True)
    elif _args.transport == "sse":
        print(f"[vClinic MCP] Serving SSE on http://{_args.host}:{_args.port}/sse", flush=True)
    mcp.run(transport=_args.transport)
