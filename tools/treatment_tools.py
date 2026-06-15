"""Medication/Treatment CRUD tools for vClinic MCP server."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_treatment(
    visit_id: str,
    patient_id: str,
    doctor_id: str,
    treatment_type: str,
    description: str,
    medication_name: Optional[str] = None,
    dosage: Optional[str] = None,
    frequency: Optional[str] = None,
    duration: Optional[str] = None,
    instructions: Optional[str] = None,
) -> dict:
    """Prescribe a treatment or medication. Returns treatment_id and created_at.

    Maps to the medications table:
      - medication_name  → description  (the drug/treatment name)
      - description      → reasondescription  (the clinical reason / treatment plan)
    """
    treatment_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO medications
               (Id, START, PATIENT, ENCOUNTER,
                DESCRIPTION, REASONDESCRIPTION, treatment_type,
                dosage, frequency, duration, instructions, doctor_id,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (treatment_id, now, patient_id, visit_id,
             medication_name, description, treatment_type,
             dosage, frequency, duration, instructions, doctor_id,
             now, now),
        )
    return {"treatment_id": treatment_id, "created_at": now}


def update_treatment(
    treatment_id: str,
    description: Optional[str] = None,
    medication_name: Optional[str] = None,
    dosage: Optional[str] = None,
    frequency: Optional[str] = None,
    duration: Optional[str] = None,
    instructions: Optional[str] = None,
) -> dict:
    """Modify an existing medication/treatment record. Only provided fields are changed."""
    fields: dict = {}
    if description is not None:
        fields["REASONDESCRIPTION"] = description
    if medication_name is not None:
        fields["DESCRIPTION"] = medication_name
    if dosage is not None:
        fields["dosage"] = dosage
    if frequency is not None:
        fields["frequency"] = frequency
    if duration is not None:
        fields["duration"] = duration
    if instructions is not None:
        fields["instructions"] = instructions
    if not fields:
        raise ValueError("No fields provided to update.")
    updated_at = _now()
    fields["updated_at"] = updated_at
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [treatment_id]
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE medications SET {set_clause} WHERE Id = ?", values
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Treatment '{treatment_id}' not found.")
    return {"treatment_id": treatment_id, "updated_at": updated_at}


def get_treatments_for_visit(visit_id: str) -> dict:
    """List all medications/treatments prescribed for a visit."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT Id AS treatment_id, ENCOUNTER AS visit_id, PATIENT AS patient_id,
                      doctor_id, treatment_type,
                      REASONDESCRIPTION AS description, DESCRIPTION AS medication_name,
                      dosage, frequency, duration, instructions,
                      created_at, updated_at
               FROM medications WHERE ENCOUNTER = ? ORDER BY created_at""",
            (visit_id,),
        ).fetchall()
    return {"treatments": [dict(r) for r in rows]}
