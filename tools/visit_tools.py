"""Visit/Encounter CRUD tools for vClinic MCP server."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from backend.db import get_connection
from cache.decorators import cached, invalidates
from cache.keys import patient_visits_key, visit_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_vital_signs(vital_signs: Optional[Union[str, dict]]) -> Optional[str]:
    """Accept vital_signs as a JSON string or a dict; always return a JSON string."""
    if vital_signs is None:
        return None
    if isinstance(vital_signs, dict):
        return json.dumps(vital_signs)
    return vital_signs


@invalidates([
    ("patient_visits", lambda patient_id, **_: patient_visits_key(patient_id)),
])
def create_visit(
    patient_id: str,
    doctor_id: str,
    chief_complaint: Optional[str] = None,
    symptoms: Optional[str] = None,
    vital_signs: Optional[Union[str, dict]] = None,
    medical_history: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Open a new patient encounter. Returns visit_id and visit_date."""
    visit_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO encounters
               (Id, START, PATIENT, ordering_doctor_id,
                chief_complaint, symptoms, vital_signs, medical_history,
                status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
            (visit_id, now, patient_id, doctor_id,
             chief_complaint, symptoms, _serialize_vital_signs(vital_signs), medical_history,
             notes, now, now),
        )
    return {"visit_id": visit_id, "visit_date": now}


@cached(namespace="visits", key_fn=lambda visit_id, **_: visit_key(visit_id))
def get_visit(visit_id: str) -> dict:
    """Retrieve an encounter record by visit_id."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT Id AS visit_id, START AS visit_date, STOP,
                      PATIENT AS patient_id, ordering_doctor_id AS doctor_id,
                      ENCOUNTERCLASS, CODE, DESCRIPTION,
                      chief_complaint, symptoms, vital_signs, medical_history,
                      status, notes, REASONCODE, REASONDESCRIPTION,
                      created_at, updated_at
               FROM encounters WHERE Id = ?""",
            (visit_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Visit '{visit_id}' not found.")
    return dict(row)


@cached(namespace="patient_visits", key_fn=lambda patient_id, **_: patient_visits_key(patient_id))
def get_visits_for_patient(patient_id: str) -> dict:
    """List all encounters for a patient, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT Id AS visit_id, START AS visit_date, STOP,
                      PATIENT AS patient_id, ordering_doctor_id AS doctor_id,
                      chief_complaint, symptoms, vital_signs,
                      status, notes, created_at, updated_at
               FROM encounters WHERE PATIENT = ? ORDER BY START DESC""",
            (patient_id,),
        ).fetchall()
    return {"visits": [dict(r) for r in rows]}


@invalidates([
    ("visits", lambda visit_id, **_: visit_key(visit_id)),
    ("patient_visits", None),  # patient_id not available among update_visit args
])
def update_visit(
    visit_id: str,
    chief_complaint: Optional[str] = None,
    symptoms: Optional[str] = None,
    vital_signs: Optional[Union[str, dict]] = None,
    medical_history: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Update mutable fields of an encounter. Only provided fields are changed."""
    fields = {
        "chief_complaint": chief_complaint,
        "symptoms": symptoms,
        "vital_signs": _serialize_vital_signs(vital_signs),
        "medical_history": medical_history,
        "status": status,
        "notes": notes,
    }
    updates = {k: v for k, v in fields.items() if v is not None}
    if not updates:
        raise ValueError("No fields provided to update.")
    updated_at = _now()
    updates["updated_at"] = updated_at
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [visit_id]
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE encounters SET {set_clause} WHERE Id = ?", values
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Visit '{visit_id}' not found.")
    return {"visit_id": visit_id, "updated_at": updated_at}
