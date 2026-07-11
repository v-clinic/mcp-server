"""Cache configuration: TTL tiers and per-namespace sizing.

All values are overridable via environment variables so operators can tune
the cache without a code change or redeploy.

Tiers (see cache-design.md §2):
  - "clinical"  — short TTL, write-through invalidation is the primary
                  consistency mechanism; TTL is a safety net only.
  - "knowledge" — long TTL; RAG/PubMed/guidelines have no write path in this
                  server, so TTL is the sole consistency mechanism.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tier TTLs (seconds)
# ---------------------------------------------------------------------------

TTL_CLINICAL = int(os.environ.get("CACHE_TTL_CLINICAL", "60"))
TTL_KNOWLEDGE = int(os.environ.get("CACHE_TTL_KNOWLEDGE", "86400"))


@dataclass(frozen=True)
class NamespaceConfig:
    name: str
    tier: str          # "clinical" | "knowledge"
    maxsize: int
    ttl: int


def _maxsize(namespace: str, default: int) -> int:
    env_key = f"CACHE_MAXSIZE_{namespace.upper()}"
    return int(os.environ.get(env_key, str(default)))


# ---------------------------------------------------------------------------
# Namespace registry — one entry per cached read operation family.
# ---------------------------------------------------------------------------

_TIER1_DEFAULTS: dict[str, int] = {
    "patients": 500,
    "patient_search": 200,
    "visits": 1000,
    "patient_visits": 500,
    "diagnoses": 2000,
    "treatments": 2000,
    "lab_orders": 1000,
    "pending_lab_orders": 200,
    "lab_results": 2000,
    "radiology_orders": 500,
    "pending_rad_orders": 100,
    "radiology_reports": 500,
}

_TIER2_DEFAULTS: dict[str, int] = {
    "rag_search": 500,
    "pubmed_search": 500,
    "clinical_guidelines": 500,
}


def build_namespace_configs() -> dict[str, NamespaceConfig]:
    """Build the full namespace -> NamespaceConfig map, applying env overrides."""
    configs: dict[str, NamespaceConfig] = {}
    for name, default_size in _TIER1_DEFAULTS.items():
        configs[name] = NamespaceConfig(
            name=name, tier="clinical", maxsize=_maxsize(name, default_size), ttl=TTL_CLINICAL
        )
    for name, default_size in _TIER2_DEFAULTS.items():
        configs[name] = NamespaceConfig(
            name=name, tier="knowledge", maxsize=_maxsize(name, default_size), ttl=TTL_KNOWLEDGE
        )
    return configs


NAMESPACE_CONFIGS: dict[str, NamespaceConfig] = build_namespace_configs()
