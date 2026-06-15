"""Radiology order and imaging study tools for vClinic MCP server.

Radiology orders are tracked in the operational `radiology_orders` table.
Reports are stored in the Synthea-aligned `imaging_studies` table
with additional operational columns (findings, impression, etc.).
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Radiology Orders
# ---------------------------------------------------------------------------

def create_radiology_order(
    visit_id: str,
    patient_id: str,
    ordering_doctor_id: str,
    study_type: str,
    body_part: str,
    clinical_indication: Optional[str] = None,
    priority: str = "routine",
) -> dict:
    """Order an imaging study. Returns order_id and ordered_at."""
    order_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO radiology_orders
               (order_id, encounter, patient, ordering_doctor_id,
                study_type, body_part, clinical_indication, priority,
                status, ordered_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (order_id, visit_id, patient_id, ordering_doctor_id,
             study_type, body_part, clinical_indication, priority, now, now),
        )
    return {"order_id": order_id, "ordered_at": now}


def get_radiology_order(order_id: str) -> dict:
    """Get a specific radiology order by order_id."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT order_id, encounter AS visit_id, patient AS patient_id,
                      ordering_doctor_id, study_type, body_part, clinical_indication,
                      priority, status, ordered_at, updated_at
               FROM radiology_orders WHERE order_id = ?""",
            (order_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Radiology order '{order_id}' not found.")
    return dict(row)


def get_pending_radiology_orders(visit_id: Optional[str] = None) -> dict:
    """List all radiology orders with status 'pending' or 'in_progress', oldest first.
    If visit_id is provided, only returns orders for that visit.
    """
    with get_connection() as conn:
        if visit_id:
            rows = conn.execute(
                """SELECT ro.order_id, ro.encounter AS visit_id,
                          ro.patient AS patient_id,
                          p.first AS first_name, p.last AS last_name,
                          ro.ordering_doctor_id, ro.study_type, ro.body_part,
                          ro.clinical_indication, ro.priority, ro.status, ro.ordered_at
                   FROM radiology_orders ro
                   JOIN patients p ON p.id = ro.patient
                   WHERE ro.status IN ('pending', 'in_progress')
                     AND ro.encounter = ?
                   ORDER BY ro.priority DESC, ro.ordered_at ASC""",
                (visit_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ro.order_id, ro.encounter AS visit_id,
                          ro.patient AS patient_id,
                          p.first AS first_name, p.last AS last_name,
                          ro.ordering_doctor_id, ro.study_type, ro.body_part,
                          ro.clinical_indication, ro.priority, ro.status, ro.ordered_at
                   FROM radiology_orders ro
                   JOIN patients p ON p.id = ro.patient
                   WHERE ro.status IN ('pending', 'in_progress')
                   ORDER BY ro.priority DESC, ro.ordered_at ASC""",
            ).fetchall()
    return {"orders": [dict(r) for r in rows]}


def update_radiology_order_status(order_id: str, status: str) -> dict:
    """Update the status of a radiology order (pending → in_progress → completed | cancelled)."""
    allowed = {"pending", "in_progress", "completed", "cancelled"}
    if status not in allowed:
        raise ValueError(f"Invalid status '{status}'. Must be one of {allowed}.")
    updated_at = _now()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE radiology_orders SET status = ?, updated_at = ? WHERE order_id = ?",
            (status, updated_at, order_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Radiology order '{order_id}' not found.")
    return {"order_id": order_id, "status": status, "updated_at": updated_at}


# ---------------------------------------------------------------------------
# Radiology Reports  (stored in imaging_studies with operational columns)
# ---------------------------------------------------------------------------

def create_radiology_report(
    order_id: str,
    patient_id: str,
    radiologist_id: str,
    findings: str,
    impression: str,
    recommendations: Optional[str] = None,
    is_critical: bool = False,
) -> dict:
    """Submit a radiology report for an imaging study. Returns report_id and performed_at."""
    report_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        order_row = conn.execute(
            "SELECT encounter, study_type, body_part FROM radiology_orders WHERE order_id = ?",
            (order_id,)
        ).fetchone()
        if order_row is None:
            raise ValueError(f"Radiology order '{order_id}' not found.")
        encounter_id = order_row["encounter"]
        study_type = order_row["study_type"]
        body_part = order_row["body_part"]
        conn.execute(
            """INSERT INTO imaging_studies
               (Id, DATE, PATIENT, ENCOUNTER,
                BODYSITE_DESCRIPTION, MODALITY_DESCRIPTION,
                order_id, radiologist_id, findings, impression, recommendations,
                is_critical, performed_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_id, now, patient_id, encounter_id,
             body_part, study_type,
             order_id, radiologist_id, findings, impression, recommendations,
             1 if is_critical else 0, now, now),
        )
    return {"report_id": report_id, "performed_at": now}


def get_radiology_report(
    visit_id: Optional[str] = None,
    order_id: Optional[str] = None,
) -> dict:
    """
    Retrieve radiology report(s) for a visit or a specific order.
    At least one of visit_id or order_id must be provided.
    """
    if not visit_id and not order_id:
        raise ValueError("Provide at least one of visit_id or order_id.")
    with get_connection() as conn:
        if order_id:
            rows = conn.execute(
                """SELECT Id AS report_id, order_id, PATIENT AS patient_id,
                          ENCOUNTER AS visit_id, radiologist_id,
                          BODYSITE_DESCRIPTION AS body_part,
                          MODALITY_DESCRIPTION AS study_type,
                          findings, impression, recommendations, is_critical,
                          performed_at, updated_at
                   FROM imaging_studies WHERE order_id = ? ORDER BY performed_at""",
                (order_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT Id AS report_id, order_id, PATIENT AS patient_id,
                          ENCOUNTER AS visit_id, radiologist_id,
                          BODYSITE_DESCRIPTION AS body_part,
                          MODALITY_DESCRIPTION AS study_type,
                          findings, impression, recommendations, is_critical,
                          performed_at, updated_at
                   FROM imaging_studies
                   WHERE ENCOUNTER = ? AND findings IS NOT NULL
                   ORDER BY performed_at""",
                (visit_id,),
            ).fetchall()
    return {"reports": [dict(r) for r in rows]}


def update_radiology_report(
    report_id: str,
    findings: Optional[str] = None,
    impression: Optional[str] = None,
    recommendations: Optional[str] = None,
    is_critical: Optional[bool] = None,
) -> dict:
    """Amend a radiology report. Only provided fields are changed."""
    fields: dict = {}
    if findings is not None:
        fields["findings"] = findings
    if impression is not None:
        fields["impression"] = impression
    if recommendations is not None:
        fields["recommendations"] = recommendations
    if is_critical is not None:
        fields["is_critical"] = 1 if is_critical else 0
    if not fields:
        raise ValueError("No fields provided to update.")
    updated_at = _now()
    fields["updated_at"] = updated_at
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [report_id]
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE imaging_studies SET {set_clause} WHERE Id = ?", values
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Radiology report '{report_id}' not found.")
    return {"report_id": report_id, "updated_at": updated_at}
