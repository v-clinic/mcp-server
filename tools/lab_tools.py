"""Lab order and result tools for vClinic MCP server.

Lab orders are tracked in the operational `lab_orders` table.
Results are stored as rows in the Synthea-aligned `observations` table
(category='laboratory') linked back via order_id.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.db import get_connection
from cache.decorators import cached, invalidates
from cache.keys import lab_order_key, lab_results_key, pending_lab_orders_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Lab Orders
# ---------------------------------------------------------------------------

@invalidates([
    ("pending_lab_orders", lambda visit_id, **_: pending_lab_orders_key(visit_id)),
    ("pending_lab_orders", lambda **_: pending_lab_orders_key(None)),
])
def create_lab_order(
    visit_id: str,
    patient_id: str,
    ordering_doctor_id: str,
    test_name: str,
    test_code: Optional[str] = None,
    clinical_notes: Optional[str] = None,
    priority: str = "routine",
) -> dict:
    """Order a lab test for a patient visit. Returns order_id and ordered_at."""
    order_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO lab_orders
               (order_id, encounter, patient, ordering_doctor_id,
                test_name, test_code, clinical_notes, priority,
                status, ordered_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (order_id, visit_id, patient_id, ordering_doctor_id,
             test_name, test_code, clinical_notes, priority, now, now),
        )
    return {"order_id": order_id, "ordered_at": now}


@cached(namespace="lab_orders", key_fn=lambda order_id, **_: lab_order_key(order_id))
def get_lab_order(order_id: str) -> dict:
    """Get a specific lab order by order_id."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT order_id, encounter AS visit_id, patient AS patient_id,
                      ordering_doctor_id, test_name, test_code, clinical_notes,
                      priority, status, ordered_at, updated_at
               FROM lab_orders WHERE order_id = ?""",
            (order_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Lab order '{order_id}' not found.")
    return dict(row)


@cached(namespace="pending_lab_orders", key_fn=lambda visit_id=None, **_: pending_lab_orders_key(visit_id))
def get_pending_lab_orders(visit_id: Optional[str] = None) -> dict:
    """List all lab orders with status 'pending' or 'in_progress', oldest first.
    If visit_id is provided, only returns orders for that visit.
    """
    with get_connection() as conn:
        if visit_id:
            rows = conn.execute(
                """SELECT lo.order_id, lo.encounter AS visit_id,
                          lo.patient AS patient_id,
                          p.first AS first_name, p.last AS last_name,
                          lo.ordering_doctor_id, lo.test_name, lo.test_code,
                          lo.clinical_notes, lo.priority, lo.status, lo.ordered_at
                   FROM lab_orders lo
                   JOIN patients p ON p.id = lo.patient
                   WHERE lo.status IN ('pending', 'in_progress')
                     AND lo.encounter = ?
                   ORDER BY lo.priority DESC, lo.ordered_at ASC""",
                (visit_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT lo.order_id, lo.encounter AS visit_id,
                          lo.patient AS patient_id,
                          p.first AS first_name, p.last AS last_name,
                          lo.ordering_doctor_id, lo.test_name, lo.test_code,
                          lo.clinical_notes, lo.priority, lo.status, lo.ordered_at
                   FROM lab_orders lo
                   JOIN patients p ON p.id = lo.patient
                   WHERE lo.status IN ('pending', 'in_progress')
                   ORDER BY lo.priority DESC, lo.ordered_at ASC""",
            ).fetchall()
    return {"orders": [dict(r) for r in rows]}


@invalidates([
    ("lab_orders", lambda order_id, **_: lab_order_key(order_id)),
    ("pending_lab_orders", None),
])
def update_lab_order_status(order_id: str, status: str) -> dict:
    """Update the status of a lab order (pending → in_progress → completed | cancelled)."""
    allowed = {"pending", "in_progress", "completed", "cancelled"}
    if status not in allowed:
        raise ValueError(f"Invalid status '{status}'. Must be one of {allowed}.")
    updated_at = _now()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE lab_orders SET status = ?, updated_at = ? WHERE order_id = ?",
            (status, updated_at, order_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Lab order '{order_id}' not found.")
    return {"order_id": order_id, "status": status, "updated_at": updated_at}


# ---------------------------------------------------------------------------
# Lab Results  (stored as observations, category='laboratory')
# ---------------------------------------------------------------------------

@invalidates([
    ("lab_results", None),  # visit_id not available among create_lab_result args
])
def create_lab_result(
    order_id: str,
    patient_id: str,
    performed_by: str,
    result_data: str,
    interpretation: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Record results for a completed lab order.
    result_data should be a JSON string, e.g.:
      '[{"name": "WBC", "value": "6.2", "unit": "K/uL", "ref_range": "4.5-11.0"}]'
    Returns result_id and performed_at.
    """
    result_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        order_row = conn.execute(
            "SELECT encounter, test_name, test_code FROM lab_orders WHERE order_id = ?",
            (order_id,)
        ).fetchone()
        if order_row is None:
            raise ValueError(f"Lab order '{order_id}' not found.")
        encounter_id = order_row["encounter"]
        test_name = order_row["test_name"]
        test_code = order_row["test_code"] or ""
        conn.execute(
            """INSERT INTO observations
               (Id, DATE, PATIENT, ENCOUNTER, CATEGORY, CODE, DESCRIPTION,
                VALUE, TYPE, order_id, performed_by, interpretation, notes, created_at)
               VALUES (?, ?, ?, ?, 'laboratory', ?, ?, ?, 'text', ?, ?, ?, ?, ?)""",
            (result_id, now, patient_id, encounter_id, test_code, test_name,
             result_data, order_id, performed_by, interpretation, notes, now),
        )
    return {"result_id": result_id, "performed_at": now}


@cached(
    namespace="lab_results",
    key_fn=lambda visit_id=None, order_id=None, **_: lab_results_key(visit_id, order_id),
)
def get_lab_results(
    visit_id: Optional[str] = None,
    order_id: Optional[str] = None,
) -> dict:
    """
    Retrieve lab results for a visit or a specific order.
    At least one of visit_id or order_id must be provided.
    """
    if not visit_id and not order_id:
        raise ValueError("Provide at least one of visit_id or order_id.")
    with get_connection() as conn:
        if order_id:
            rows = conn.execute(
                """SELECT Id AS result_id, order_id, PATIENT AS patient_id,
                          ENCOUNTER AS visit_id, performed_by,
                          DESCRIPTION AS test_name, VALUE AS result_data,
                          interpretation, notes, DATE AS performed_at, created_at
                   FROM observations
                   WHERE order_id = ? AND CATEGORY = 'laboratory'
                   ORDER BY DATE""",
                (order_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT Id AS result_id, order_id, PATIENT AS patient_id,
                          ENCOUNTER AS visit_id, performed_by,
                          DESCRIPTION AS test_name, VALUE AS result_data,
                          interpretation, notes, DATE AS performed_at, created_at
                   FROM observations
                   WHERE ENCOUNTER = ? AND CATEGORY = 'laboratory'
                   ORDER BY DATE""",
                (visit_id,),
            ).fetchall()
    return {"results": [dict(r) for r in rows]}


@invalidates([
    ("lab_results", None),  # visit_id not available among update_lab_result args
])
def update_lab_result(
    result_id: str,
    result_data: Optional[str] = None,
    interpretation: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Amend a lab result record. Only provided fields are changed."""
    fields: dict = {}
    if result_data is not None:
        fields["VALUE"] = result_data
    if interpretation is not None:
        fields["interpretation"] = interpretation
    if notes is not None:
        fields["notes"] = notes
    if not fields:
        raise ValueError("No fields provided to update.")
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [result_id]
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE observations SET {set_clause} WHERE Id = ? AND CATEGORY = 'laboratory'",
            values
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Lab result '{result_id}' not found.")
    return {"result_id": result_id}
