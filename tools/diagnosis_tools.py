"""Condition (diagnosis) CRUD tools for vClinic MCP server."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_diagnosis(
    visit_id: str,
    patient_id: str,
    doctor_id: str,
    description: str,
    icd_code: Optional[str] = None,
    severity: Optional[str] = None,
    is_preliminary: bool = True,
) -> dict:
    """Record a diagnosis/condition for a visit. Returns diagnosis_id and created_at."""
    diagnosis_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO conditions
               (Id, START, PATIENT, ENCOUNTER, SYSTEM, CODE, DESCRIPTION,
                severity, is_preliminary, doctor_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'ICD-10', ?, ?, ?, ?, ?, ?, ?)""",
            (diagnosis_id, now, patient_id, visit_id, icd_code, description,
             severity, 1 if is_preliminary else 0, doctor_id, now, now),
        )
    return {"diagnosis_id": diagnosis_id, "created_at": now}


def update_diagnosis(
    diagnosis_id: str,
    description: Optional[str] = None,
    icd_code: Optional[str] = None,
    severity: Optional[str] = None,
    is_preliminary: Optional[bool] = None,
) -> dict:
    """Update or finalize a diagnosis. Only provided fields are changed."""
    fields: dict = {}
    if description is not None:
        fields["DESCRIPTION"] = description
    if icd_code is not None:
        fields["CODE"] = icd_code
    if severity is not None:
        fields["severity"] = severity
    if is_preliminary is not None:
        fields["is_preliminary"] = 1 if is_preliminary else 0
    if not fields:
        raise ValueError("No fields provided to update.")
    updated_at = _now()
    fields["updated_at"] = updated_at
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [diagnosis_id]
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE conditions SET {set_clause} WHERE Id = ?", values
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Diagnosis '{diagnosis_id}' not found.")
    return {"diagnosis_id": diagnosis_id, "updated_at": updated_at}


def get_diagnoses_for_visit(visit_id: str) -> dict:
    """Retrieve all diagnoses/conditions for a visit, ordered by creation time."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT Id AS diagnosis_id, ENCOUNTER AS visit_id, PATIENT AS patient_id,
                      doctor_id, CODE AS icd_code, DESCRIPTION, severity,
                      is_preliminary, START, created_at, updated_at
               FROM conditions WHERE ENCOUNTER = ? ORDER BY created_at""",
            (visit_id,),
        ).fetchall()
    return {"diagnoses": [dict(r) for r in rows]}
