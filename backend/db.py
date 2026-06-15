"""
Database connection, schema initialisation, and staff seeding for vClinic.
POC and demostration with sqllite for simplicity, but can be swapped out for any DB with a Python driver.
"""

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).parent.parent / "data" / "vclinic.db"
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Open and return a SQLite connection with row_factory and FK support."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Init & seed
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables (idempotent) and seed default staff records."""
    conn = get_connection()
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()

