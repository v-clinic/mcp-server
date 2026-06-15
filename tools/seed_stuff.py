"""add new staff tools for vClinic MCP server."""

from datetime import datetime, timezone

from backend.db import get_connection

def seed_staff(
    staff_id: str,
    first_name: str,
    last_name: str,
    role: str,
    department: str,
)->dict:
    with get_connection() as conn:      
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT OR IGNORE INTO staff
               (staff_id, first_name, last_name, role, department, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (staff_id, first_name, last_name, role, department, created_at),
        )
    conn.commit()
    return {
        "staff_id": staff_id,
        "first_name": first_name,
        "last_name": last_name,
        "role": role,
        "department": department,
        "created_at": created_at,
    }
