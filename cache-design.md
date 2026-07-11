# vClinic MCP Server — Cache Layer Design

**Date:** 2026-07-10  
**Status:** Approved for implementation  
**Author:** Architecture review

---

## 1. Requirements

| # | Requirement | Implication |
|---|---|---|
| 1 | Access pattern follows a clinic visit: check-in → doctor reads/updates → lab/radiology reads/updates | Short read bursts on the same patient/visit; writes invalidate immediately |
| 2 | Zero data staleness tolerance | TTL alone is insufficient; write-through invalidation is mandatory |
| 3 | Strong consistency | Every successful write must synchronously invalidate affected cache entries before returning |
| 4 | RAG and external search are effectively static | Long TTL (hours/days); no invalidation path needed |
| 5 | Single deployment (one active instance) | In-process memory cache is sufficient; no distributed cache required |
| 6 | Cache HIT/MISS must be audited | Events written to the same `data/audit.log` CSV as all tool calls |
| 7 | Cache data is not a compliance record | Contents live only in private process memory; never written to disk or network |
| 8 | Clinical data TTL: ~1 minute | Safety net against missed invalidations and out-of-band DB changes |

---

## 2. Architecture Overview

### Two-Tier Design

```
┌──────────────────────────────────────────────────────────────────┐
│                       TIER 1: CLINICAL DATA                      │
│  TTL = 60 s  │  Write-through invalidation = mandatory           │
│                                                                  │
│  patients · patient_search · visits · patient_visits             │
│  diagnoses · treatments                                          │
│  lab_orders · pending_lab_orders · lab_results                   │
│  radiology_orders · pending_rad_orders · radiology_reports       │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     TIER 2: KNOWLEDGE DATA                       │
│  TTL = 86 400 s (24 h)  │  TTL is the sole consistency mechanism │
│                                                                  │
│  rag_search · pubmed_search · clinical_guidelines                │
└──────────────────────────────────────────────────────────────────┘
```

**Tier 1 — Clinical data:**  
The 60-second TTL is a *safety net only*. The primary consistency mechanism is explicit, synchronous write-through invalidation on every successful write. A write that raises an exception does not invalidate the cache.

**Tier 2 — Knowledge data:**  
RAG (Pinecone), PubMed, and clinical guidelines are static medical content with no write operations in this server. TTL is the only consistency mechanism needed.

### Infrastructure

- **Implementation:** [`cachetools`](https://pypi.org/project/cachetools/) `>=5.3` — pure-Python, MIT, no native extensions, no external services.
- **Concurrency:** One `threading.RLock` per namespace. Safe for FastMCP's thread-pool execution of synchronous tool functions.
- **Memory:** In-process only. Cache is cold on every process restart. No serialisation to disk.
- **Configuration:** All TTL and max-size values are overridable via environment variables without code changes.

---

## 3. Module Layout

```
cache/
├── __init__.py          ← get_cache_manager() — public singleton accessor
├── config.py            ← two-tier TTL constants, env-var overrides, per-namespace sizing
├── manager.py           ← CacheManager: per-namespace TTLCache instances + RLock
├── keys.py              ← canonical cache-key builder functions
├── metrics.py           ← thread-safe hit/miss/eviction counters per namespace
└── decorators.py        ← @cached, @invalidates
```

---

## 4. Cache Namespaces

### Tier 1 — Clinical (60 s TTL)

| Namespace | Max entries | Cached by |
|---|---|---|
| `patients` | 500 | `get_patient` |
| `patient_search` | 200 | `search_patients` |
| `visits` | 1 000 | `get_visit` |
| `patient_visits` | 500 | `get_visits_for_patient` |
| `diagnoses` | 2 000 | `get_diagnoses_for_visit` |
| `treatments` | 2 000 | `get_treatments_for_visit` |
| `lab_orders` | 1 000 | `get_lab_order` |
| `pending_lab_orders` | 200 | `get_pending_lab_orders` |
| `lab_results` | 2 000 | `get_lab_results` |
| `radiology_orders` | 500 | `get_radiology_order` |
| `pending_rad_orders` | 100 | `get_pending_radiology_orders` |
| `radiology_reports` | 500 | `get_radiology_report` |

### Tier 2 — Knowledge (86 400 s / 24 h TTL)

| Namespace | Max entries | Cached by |
|---|---|---|
| `rag_search` | 500 | `search_clinic_knowledge` |
| `pubmed_search` | 500 | `search_pubmed` |
| `clinical_guidelines` | 500 | `get_clinical_guidelines` |

### Environment Variables

```
CACHE_TTL_CLINICAL          default: 60
CACHE_TTL_KNOWLEDGE         default: 86400
CACHE_MAXSIZE_PATIENTS      default: 500
CACHE_MAXSIZE_VISITS        default: 1000
# ... one per namespace (see cache/config.py)
```

---

## 5. Cache Key Scheme

Keys contain only UUIDs or short hashes — never free-text PHI.

| Namespace | Key format | Example |
|---|---|---|
| `patients` | `patient:{uuid}` | `patient:3f2a...` |
| `patient_search` | `search:{sha256(query)[:16]}` | `search:4a7c9e12bf...` |
| `visits` | `visit:{uuid}` | `visit:8b1d...` |
| `patient_visits` | `patient_visits:{patient_uuid}` | `patient_visits:3f2a...` |
| `diagnoses` | `diagnoses:visit:{visit_uuid}` | `diagnoses:visit:8b1d...` |
| `treatments` | `treatments:visit:{visit_uuid}` | `treatments:visit:8b1d...` |
| `lab_orders` | `lab_order:{uuid}` | `lab_order:c9e3...` |
| `pending_lab_orders` | `pending_lab:{visit_uuid\|'all'}` | `pending_lab:all` |
| `lab_results` | `lab_results:{visit_uuid}:{order_uuid\|'none'}` | `lab_results:8b1d...:none` |
| `radiology_orders` | `radiology_order:{uuid}` | `radiology_order:d4f1...` |
| `pending_rad_orders` | `pending_rad:{visit_uuid\|'all'}` | `pending_rad:all` |
| `radiology_reports` | `rad_report:{visit_uuid}:{order_uuid\|'none'}` | `rad_report:8b1d...:none` |
| `rag_search` | `rag:{sha256(query+top_k)[:16]}` | `rag:99a2c4...` |
| `pubmed_search` | `pubmed:{sha256(query+max)[:16]}` | `pubmed:3ef1...` |
| `clinical_guidelines` | `guide:{sha256(condition+max)[:16]}` | `guide:77bc...` |

---

## 6. CacheManager API

```python
class CacheManager:
    def get(self, namespace: str, key: str) -> Any | None
    def set(self, namespace: str, key: str, value: Any) -> None
    def invalidate(self, namespace: str, key: str) -> None       # single key
    def flush_namespace(self, namespace: str) -> None            # entire namespace
    def stats(self) -> dict[str, CacheStats]                    # metrics per namespace
```

`get()` returns `None` on miss (never raises). `set()` is a no-op if the namespace is not configured. All methods acquire the namespace lock.

---

## 7. Decorator API

### `@cached` — wraps read functions

```python
@audit
@cached(namespace="visits", key_fn=lambda visit_id, **_: f"visit:{visit_id}")
def get_visit(visit_id: str) -> dict:
    ...
```

Behaviour:
1. Compute key via `key_fn(*args, **kwargs)`.
2. Check cache → **HIT**: log audit event, return cached value without calling the DB.
3. **MISS**: call DB, log audit event, store result, return result.
4. On any exception from the DB call: log audit event (MISS, ERROR), re-raise.

### `@invalidates` — wraps write functions

```python
@audit
@invalidates([
    ("visits",        lambda visit_id, **_: f"visit:{visit_id}"),  # key-level
    ("patient_visits", None),                                        # full flush
])
def update_visit(visit_id: str, ...) -> dict:
    ...
```

Each entry is `(namespace, key_fn)`. `key_fn=None` triggers `flush_namespace()`.

Behaviour:
1. Call the wrapped write function.
2. On **success**: iterate invalidation list synchronously, then return.
3. On **exception**: do NOT invalidate (write did not commit). Re-raise.

Both decorators preserve `__name__`, `__doc__`, and `__wrapped__` via `functools.wraps`.

---

## 8. Invalidation Map

### Legend
- **Key** — single-key invalidation (precise)
- **Flush** — entire namespace cleared

| Write tool | Namespaces | Scope | Reason |
|---|---|---|---|
| `create_patient` | `patient_search` | Flush | New patient may appear in any search |
| `create_visit(patient_id)` | `patient_visits` | Key: `patient_visits:{patient_id}` | Only that patient's visit list changes |
| `update_visit(visit_id)` | `visits`, `patient_visits` | Key `visits:{visit_id}` + Flush `patient_visits` | Visit record and list both stale |
| `create_diagnosis(visit_id)` | `diagnoses` | Key: `diagnoses:visit:{visit_id}` | Only that visit's diagnosis list changes |
| `update_diagnosis(diagnosis_id)` | `diagnoses` | **Flush** | `visit_id` not in args; safe to flush small namespace |
| `create_treatment(visit_id)` | `treatments` | Key: `treatments:visit:{visit_id}` | Only that visit's treatment list changes |
| `update_treatment(treatment_id)` | `treatments` | **Flush** | `visit_id` not in args |
| `create_lab_order(visit_id)` | `pending_lab_orders` | Key `pending_lab:{visit_id}` + Key `pending_lab:all` | Both scoped and global pending views |
| `update_lab_order_status(order_id)` | `lab_orders`, `pending_lab_orders` | Key `lab_order:{order_id}` + Flush `pending_lab_orders` | Order record stale; pending queue changes |
| `create_lab_result(visit_id, order_id)` | `lab_results` | Keys `lab_results:{visit_id}:{order_id}` and `lab_results:{visit_id}:none` | Both scoped views affected |
| `update_lab_result(result_id)` | `lab_results` | **Flush** | `visit_id` not in args |
| `create_radiology_order(visit_id)` | `pending_rad_orders` | Key `pending_rad:{visit_id}` + Key `pending_rad:all` | Both scoped and global pending views |
| `update_radiology_order_status(order_id)` | `radiology_orders`, `pending_rad_orders` | Key `radiology_order:{order_id}` + Flush `pending_rad_orders` | Order record stale; queue changes |
| `create_radiology_report(visit_id, order_id)` | `radiology_reports` | Key `rad_report:{visit_id}:{order_id}` | Only that specific report view |
| `update_radiology_report(report_id)` | `radiology_reports` | **Flush** | `visit_id` not in args |

**Why namespace flush is safe:** With a 60-second TTL and at most a few dozen concurrent visit sessions, flushing a namespace evicts at most tens of entries instantaneously. The next read repopulates from SQLite. No correctness risk; negligible performance impact.

---

## 9. Audit Log Integration

### Problem

Cache HIT/MISS occurs inside `@cached`, which executes *underneath* `@audit` in the call stack. `staff_id` and `role` are only known to `@audit`.

### Solution: `contextvars.ContextVar`

`audit_logger.py` exposes:

```python
from contextvars import ContextVar
_staff_ctx: ContextVar[tuple[str, str]] = ContextVar("staff_ctx", default=("", ""))
```

The `@audit` decorator sets it before dispatching:

```python
token = _staff_ctx.set((staff_id or "", role or ""))
try:
    result = fn(*args, **kwargs)   # @cached runs here, reads _staff_ctx
    log_tool_call(fn.__name__, call_args, "SUCCESS", staff_id=staff_id, role=role)
    return result
finally:
    _staff_ctx.reset(token)
```

### `log_cache_event()` (new function in `audit_logger.py`)

```python
def log_cache_event(
    tool_name: str,
    namespace: str,
    key: str,
    hit: bool,
) -> None:
    staff_id, role = _staff_ctx.get()
    action = "CACHE_HIT" if hit else "CACHE_MISS"
    row = [uuid4(), utc_now(), staff_id, role,
           tool_name, "", "", action, namespace,
           "SUCCESS", "", json.dumps({"key": key})]
    _append_row(row)
```

### Audit Log Schema Impact

No new CSV columns. Cache events use the **existing 12-column schema** with two new `action` values:

| Field | Cache HIT | Cache MISS |
|---|---|---|
| `action` | `CACHE_HIT` | `CACHE_MISS` |
| `resource` | namespace name (e.g., `visits`) | namespace name |
| `outcome` | `SUCCESS` | `SUCCESS` |
| `tool_name` | tool being called | tool being called |
| `staff_id` / `role` | from ContextVar | from ContextVar |
| `details` | `{"key": "visit:uuid..."}` | `{"key": "visit:uuid..."}` |
| `patient_id`, `visit_id` | empty | empty |
| `error_msg` | empty | empty |

Cache data itself is **never written** to the audit log — only the cache lookup event.

---

## 10. `get_cache_stats` MCP Tool

A new read-only tool registered in `server.py`:

```python
def get_cache_stats() -> dict:
    """Return per-namespace cache hit rates, sizes, and TTL config."""
```

Returns:
```json
{
  "patients":         { "hits": 140, "misses": 12, "hit_rate": 0.92, "current_size": 45, "max_size": 500, "ttl_s": 60 },
  "rag_search":       { "hits": 32,  "misses": 4,  "hit_rate": 0.89, "current_size": 8,  "max_size": 500, "ttl_s": 86400 },
  ...
}
```

Registered in `_TOOL_REGISTRY`:
```python
"get_cache_stats": ("READ", "internal_knowledge"),
```

---

## 11. Files Changed

| File | Type | Description |
|---|---|---|
| `cache/__init__.py` | New | Public API: `get_cache_manager()` |
| `cache/config.py` | New | TTL constants, env-var overrides, namespace sizing |
| `cache/manager.py` | New | `CacheManager` singleton, per-namespace `TTLCache` + `RLock` |
| `cache/keys.py` | New | Canonical key-builder functions |
| `cache/metrics.py` | New | Thread-safe hit/miss counters |
| `cache/decorators.py` | New | `@cached`, `@invalidates` |
| `audit_logger.py` | Modified | Add `_staff_ctx` ContextVar; set in `@audit`; add `log_cache_event()`; add `get_cache_stats` to registry |
| `tools/patient_tools.py` | Modified | `@cached` on reads, `@invalidates` on writes |
| `tools/visit_tools.py` | Modified | Same |
| `tools/diagnosis_tools.py` | Modified | Same |
| `tools/treatment_tools.py` | Modified | Same |
| `tools/lab_tools.py` | Modified | Same |
| `tools/radiology_tools.py` | Modified | Same |
| `tools/medical_search_tools.py` | Modified | `@cached` (knowledge tier, 24 h TTL) |
| `rag_tools/rag_tools.py` | Modified | `@cached` (knowledge tier, 24 h TTL) |
| `server.py` | Modified | Register `get_cache_stats()` MCP tool |
| `requirements.txt` | Modified | Add `cachetools>=5.3` |

---

## 12. HIPAA / Security Notes

- Cache keys are UUIDs or short SHA-256 digests. No PHI in keys.
- Cache values (DB rows) are in private process heap memory — same protection level as any in-flight request data.
- Cache contents are never serialised, logged, or transmitted.
- On process termination, all cached data is released with the heap.
- The audit log records *that* a lookup occurred (hit/miss, tool, namespace, key hash) — not the content of cached records.
- Access control is not relaxed by caching: the cache is populated only from data already retrieved by an authorised tool call.
