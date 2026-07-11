"""
vClinic MCP Server — entry point.

Run from the project root with:
    python -m server

Pass --reinit to wipe and recreate the database (drops all data):
    python -m server --reinit

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
# Initialise DB (creates tables + seeds default staff on first run)
# Pass --reinit on the command line to wipe and recreate the database.
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

_reinit = "--reinit" in sys.argv
_db_path = Path(__file__).parent / "data" / "vclinic.db"
if _reinit and _db_path.exists():
    _db_path.unlink()
if _reinit or not _db_path.exists():
    init_db()

# ---------------------------------------------------------------------------
# Initialise RAG collection (build or load ChromaDB index at startup)
# ---------------------------------------------------------------------------
init_rag_collection()

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("vclinic-mcp-server")

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
    mcp.run(transport="stdio")
