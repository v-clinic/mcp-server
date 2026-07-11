"""
vClinic Audit Logger — HIPAA § 164.312(b) Technical Safeguard.

Writes one CSV row per MCP tool call to `data/audit.log`.
The header is written once when the file is created; subsequent runs append rows.
The file is opened in append mode on every write — never truncated or rewritten.

Usage (via decorator — preferred):
    from mcp_server.audit_logger import audit

    @audit
    def create_patient(...):
        ...

Direct usage:
    from mcp_server.audit_logger import log_tool_call
    log_tool_call("create_patient", args={"patient_id": "..."}, outcome="SUCCESS")
"""

from __future__ import annotations

import csv
import fcntl
import functools
import io
import json
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_LOG_PATH = Path(__file__).resolve().parent / "data" / "audit.log"

# Set by the @audit decorator around each tool call; read by log_cache_event()
# so that cache HIT/MISS events (logged from inside @cached, several stack
# frames below @audit) can still be attributed to the calling staff member.
_staff_ctx: ContextVar[tuple[str, str]] = ContextVar("staff_ctx", default=("", ""))

_CSV_FIELDS = [
    "log_id", "timestamp", "staff_id", "role", "tool_name",
    "patient_id", "visit_id", "action", "resource",
    "outcome", "error_msg", "details",
]

# ---------------------------------------------------------------------------
# Tool registry — maps each tool name to (action, resource)
# Used to populate structured fields without parsing free-text.
# ---------------------------------------------------------------------------
_TOOL_REGISTRY: dict[str, tuple[str, str]] = {
    # Patient
    "create_patient":              ("CREATE", "patient"),
    "get_patient":                 ("READ",   "patient"),
    "search_patients":             ("READ",   "patient"),
    # Visit
    "create_visit":                ("CREATE", "visit"),
    "get_visit":                   ("READ",   "visit"),
    "get_visits_for_patient":      ("READ",   "visit"),
    "update_visit":                ("UPDATE", "visit"),
    # Diagnosis
    "create_diagnosis":            ("CREATE", "diagnosis"),
    "update_diagnosis":            ("UPDATE", "diagnosis"),
    "get_diagnoses_for_visit":     ("READ",   "diagnosis"),
    # Treatment
    "create_treatment":            ("CREATE", "treatment"),
    "update_treatment":            ("UPDATE", "treatment"),
    "get_treatments_for_visit":    ("READ",   "treatment"),
    # Lab
    "create_lab_order":            ("CREATE", "lab"),
    "get_lab_order":               ("READ",   "lab"),
    "get_pending_lab_orders":      ("READ",   "lab"),
    "update_lab_order_status":     ("UPDATE", "lab"),
    "create_lab_result":           ("CREATE", "lab"),
    "get_lab_results":             ("READ",   "lab"),
    "update_lab_result":           ("UPDATE", "lab"),
    # Radiology
    "create_radiology_order":      ("CREATE", "radiology"),
    "get_radiology_order":         ("READ",   "radiology"),
    "get_pending_radiology_orders":("READ",   "radiology"),
    "update_radiology_order_status":("UPDATE","radiology"),
    "create_radiology_report":     ("CREATE", "radiology"),
    "get_radiology_report":        ("READ",   "radiology"),
    "update_radiology_report":     ("UPDATE", "radiology"),
    # Knowledge
    "search_pubmed":               ("READ",   "external_knowledge"),
    "get_clinical_guidelines":     ("READ",   "external_knowledge"),
    "search_clinic_knowledge":     ("READ",   "internal_knowledge"),
    # Cache observability
    "get_cache_stats":             ("READ",   "internal_knowledge"),
}

# Keys whose values are safe to store in `details` (no free-text PHI)
_SAFE_KEYS = {
    "patient_id", "visit_id", "order_id", "result_id", "report_id",
    "diagnosis_id", "treatment_id", "staff_id", "doctor_id",
    "ordering_doctor_id", "radiologist_id", "performed_by",
    "status", "priority", "test_code", "study_type", "body_part",
    "icd_code", "treatment_type", "is_preliminary", "is_critical",
    "interpretation", "query", "condition", "max_results",
}


def _safe_details(args: dict[str, Any]) -> str:
    """Return a compact JSON string of args, keeping only non-PHI keys."""
    safe = {k: v for k, v in args.items() if k in _SAFE_KEYS}
    return json.dumps(safe, separators=(",", ":"), default=str)


def _extract_ids(args: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Pull patient_id and visit_id out of tool args if present."""
    patient_id = args.get("patient_id") or args.get("patient_id")
    visit_id = args.get("visit_id")
    return patient_id, visit_id


def log_tool_call(
    tool_name: str,
    args: dict[str, Any],
    outcome: str,                        # "SUCCESS" | "ERROR"
    staff_id: Optional[str] = None,
    role: Optional[str] = None,
    error_msg: Optional[str] = None,
) -> None:
    """Append one CSV row to the audit log file. Never raises — errors are printed only."""
    try:
        action, resource = _TOOL_REGISTRY.get(tool_name, ("CALL", "unknown"))
        patient_id, visit_id = _extract_ids(args)
        row = [
            str(uuid.uuid4()),
            datetime.now(timezone.utc).isoformat(),
            staff_id or "",
            role or "",
            tool_name,
            patient_id or "",
            visit_id or "",
            action,
            resource,
            outcome,
            error_msg or "",
            _safe_details(args),
        ]
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_header = not _LOG_PATH.exists() or _LOG_PATH.stat().st_size == 0
        with _LOG_PATH.open("a", encoding="utf-8", newline="") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                writer = csv.writer(fh)
                if write_header:
                    writer.writerow(_CSV_FIELDS)
                writer.writerow(row)
                fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except Exception as exc:
        print(f"[AUDIT ERROR] Failed to write audit log for '{tool_name}': {exc}", flush=True)


def log_cache_event(tool_name: str, namespace: str, key: str, hit: bool) -> None:
    """Append one CACHE_HIT/CACHE_MISS row to the audit log. Never raises.

    Reuses the existing 12-column schema — no new columns are introduced.
    `resource` carries the cache namespace; `details` carries the cache key
    only (never the cached value, never PHI). staff_id/role come from the
    ContextVar set by the enclosing @audit call.
    """
    try:
        staff_id, role = _staff_ctx.get()
        action = "CACHE_HIT" if hit else "CACHE_MISS"
        row = [
            str(uuid.uuid4()),
            datetime.now(timezone.utc).isoformat(),
            staff_id or "",
            role or "",
            tool_name,
            "",
            "",
            action,
            namespace,
            "SUCCESS",
            "",
            json.dumps({"key": key}, separators=(",", ":")),
        ]
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_header = not _LOG_PATH.exists() or _LOG_PATH.stat().st_size == 0
        with _LOG_PATH.open("a", encoding="utf-8", newline="") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                writer = csv.writer(fh)
                if write_header:
                    writer.writerow(_CSV_FIELDS)
                writer.writerow(row)
                fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except Exception as exc:
        print(f"[AUDIT ERROR] Failed to write cache event for '{tool_name}': {exc}", flush=True)


def audit(fn: Callable) -> Callable:
    """Decorator that wraps an MCP tool function with audit logging.

    Extracts staff_id / role from kwargs when present. On exception the error
    is logged and re-raised so the tool still returns the error to the caller.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        staff_id = (
            kwargs.get("staff_id")
            or kwargs.get("doctor_id")
            or kwargs.get("ordering_doctor_id")
            or kwargs.get("radiologist_id")
            or kwargs.get("performed_by")
        )
        call_args = {**kwargs}
        # Include positional args by name using the function signature
        import inspect
        sig = inspect.signature(fn)
        param_names = list(sig.parameters.keys())
        for i, val in enumerate(args):
            if i < len(param_names):
                call_args[param_names[i]] = val

        role = kwargs.get("role")
        token = _staff_ctx.set((staff_id or "", role or ""))
        try:
            result = fn(*args, **kwargs)
            log_tool_call(fn.__name__, call_args, "SUCCESS", staff_id=staff_id, role=role)
            return result
        except Exception as exc:
            log_tool_call(fn.__name__, call_args, "ERROR",
                          staff_id=staff_id, role=role, error_msg=str(exc))
            raise
        finally:
            _staff_ctx.reset(token)

    return wrapper
