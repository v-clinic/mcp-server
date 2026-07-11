"""Patient CRUD tools for vClinic MCP server."""

import uuid
from typing import Optional

from backend.db import get_connection
from cache.decorators import cached, invalidates
from cache.keys import patient_key, patient_search_key


@invalidates([
    ("patient_search", None),  # new patient may match any existing search
])
def create_patient(
    first_name: str,
    last_name: str,
    date_of_birth: str,
    gender: Optional[str] = None,
    prefix: Optional[str] = None,
    middle: Optional[str] = None,
    suffix: Optional[str] = None,
    address: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip: Optional[str] = None,
    race: Optional[str] = None,
    ethnicity: Optional[str] = None,
    marital: Optional[str] = None,
) -> dict:
    """Create a new patient record. Returns patient_id."""
    patient_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO patients
               (Id, FIRST, LAST, BIRTHDATE, GENDER,
                PREFIX, MIDDLE, SUFFIX, ADDRESS, CITY, STATE, ZIP,
                RACE, ETHNICITY, MARITAL)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, first_name, last_name, date_of_birth, gender,
             prefix, middle, suffix, address, city, state, zip,
             race, ethnicity, marital),
        )
    return {"patient_id": patient_id}


@cached(namespace="patients", key_fn=lambda patient_id, **_: patient_key(patient_id))
def get_patient(patient_id: str) -> dict:
    """Retrieve a patient record by patient_id."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT Id AS patient_id, FIRST AS first_name, LAST AS last_name,
                      BIRTHDATE AS date_of_birth, GENDER, PREFIX, MIDDLE, SUFFIX,
                      ADDRESS, CITY, STATE, ZIP, RACE, ETHNICITY, MARITAL,
                      MAIDEN, SSN, BIRTHPLACE, LAT, LON,
                      HEALTHCARE_EXPENSES, HEALTHCARE_COVERAGE, INCOME
               FROM patients WHERE Id = ?""",
            (patient_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Patient '{patient_id}' not found.")
    return dict(row)


@cached(namespace="patient_search", key_fn=lambda query, **_: patient_search_key(query))
def search_patients(query: str) -> dict:
    """Search patients by partial first name, last name, full name, or date of birth (YYYY-MM-DD)."""
    like = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT Id AS patient_id, FIRST AS first_name, LAST AS last_name,
                      BIRTHDATE AS date_of_birth, GENDER, ADDRESS, CITY, STATE
               FROM patients
               WHERE FIRST LIKE ?
                  OR LAST  LIKE ?
                  OR (FIRST || ' ' || LAST) LIKE ?
                  OR BIRTHDATE LIKE ?
               ORDER BY LAST, FIRST""",
            (like, like, like, like),
        ).fetchall()
    return {"patients": [dict(r) for r in rows]}
