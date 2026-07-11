"""Canonical cache-key builder functions.

Keys must never contain free-text PHI. Patient/visit/order identifiers are
UUIDs (safe by construction, non-reversible on their own). Free-text search
queries are hashed to a short, fixed-length digest.
"""

from __future__ import annotations

import hashlib
import json


def is_json_success(result: object) -> bool:
    """Return False for JSON-string results that encode an {"error": ...} payload.

    Several external-facing tools (PubMed, RAG) catch exceptions internally and
    return a JSON string like '{"error": "..."}' instead of raising. Without
    this check, a transient network failure would otherwise be cached for the
    full knowledge-tier TTL (up to 24h).
    """
    if not isinstance(result, str):
        return True
    try:
        parsed = json.loads(result)
    except (ValueError, TypeError):
        return True
    return not (isinstance(parsed, dict) and "error" in parsed)


def hash_text(*parts: object) -> str:
    """Return a short, stable digest for arbitrary free-text query args.

    Used so that raw search strings (which could theoretically contain
    incidental PHI typed by a clinician) never appear verbatim in a cache key
    or in the audit log's `details` field.
    """
    joined = "|".join(str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def patient_key(patient_id: str) -> str:
    return f"patient:{patient_id}"


def patient_search_key(query: str) -> str:
    return f"search:{hash_text(query)}"


def visit_key(visit_id: str) -> str:
    return f"visit:{visit_id}"


def patient_visits_key(patient_id: str) -> str:
    return f"patient_visits:{patient_id}"


def diagnoses_key(visit_id: str) -> str:
    return f"diagnoses:visit:{visit_id}"


def treatments_key(visit_id: str) -> str:
    return f"treatments:visit:{visit_id}"


def lab_order_key(order_id: str) -> str:
    return f"lab_order:{order_id}"


def pending_lab_orders_key(visit_id: str | None) -> str:
    return f"pending_lab:{visit_id or 'all'}"


def lab_results_key(visit_id: str | None, order_id: str | None) -> str:
    return f"lab_results:{visit_id or 'none'}:{order_id or 'none'}"


def radiology_order_key(order_id: str) -> str:
    return f"radiology_order:{order_id}"


def pending_rad_orders_key(visit_id: str | None) -> str:
    return f"pending_rad:{visit_id or 'all'}"


def radiology_reports_key(visit_id: str | None, order_id: str | None) -> str:
    return f"rad_report:{visit_id or 'none'}:{order_id or 'none'}"


def rag_search_key(query: str, max_results: int) -> str:
    return f"rag:{hash_text(query, max_results)}"


def pubmed_search_key(query: str, max_results: int) -> str:
    return f"pubmed:{hash_text(query, max_results)}"


def clinical_guidelines_key(condition: str, max_results: int) -> str:
    return f"guide:{hash_text(condition, max_results)}"
