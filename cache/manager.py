"""In-process cache manager.

Single-deployment design: one CacheManager singleton per server process.
Each namespace owns its own cachetools.TTLCache plus a dedicated RLock, so a
slow operation in one namespace never blocks another.

Cached values live only in process heap memory. Nothing is written to disk
or transmitted anywhere, satisfying the "not a compliance record" requirement.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from cachetools import TTLCache

from cache.config import NAMESPACE_CONFIGS, NamespaceConfig
from cache.metrics import CacheStats, NamespaceMetrics

_SENTINEL = object()


class _Namespace:
    __slots__ = ("config", "store", "lock", "metrics")

    def __init__(self, config: NamespaceConfig) -> None:
        self.config = config
        self.store: TTLCache = TTLCache(maxsize=config.maxsize, ttl=config.ttl)
        self.lock = threading.RLock()
        self.metrics = NamespaceMetrics(maxsize=config.maxsize, ttl=config.ttl)


class CacheManager:
    """Process-wide, namespace-partitioned TTL cache.

    Not intended to be instantiated directly outside of tests — use
    get_cache_manager() to obtain the shared singleton.
    """

    def __init__(self) -> None:
        self._namespaces: dict[str, _Namespace] = {
            name: _Namespace(cfg) for name, cfg in NAMESPACE_CONFIGS.items()
        }

    def _ns(self, namespace: str) -> Optional[_Namespace]:
        return self._namespaces.get(namespace)

    def get(self, namespace: str, key: str) -> Any:
        """Return the cached value, or None on miss (unknown namespace is a miss)."""
        ns = self._ns(namespace)
        if ns is None:
            return None
        with ns.lock:
            value = ns.store.get(key, _SENTINEL)
        if value is _SENTINEL:
            ns.metrics.record_miss()
            return None
        ns.metrics.record_hit()
        return value

    def set(self, namespace: str, key: str, value: Any) -> None:
        """Store a value. No-op if the namespace is not configured."""
        ns = self._ns(namespace)
        if ns is None:
            return
        with ns.lock:
            ns.store[key] = value

    def invalidate(self, namespace: str, key: str) -> None:
        """Remove a single key. Safe to call for a key that isn't present."""
        ns = self._ns(namespace)
        if ns is None:
            return
        with ns.lock:
            ns.store.pop(key, None)

    def flush_namespace(self, namespace: str) -> None:
        """Clear every entry in a namespace."""
        ns = self._ns(namespace)
        if ns is None:
            return
        with ns.lock:
            ns.store.clear()

    def stats(self) -> dict[str, dict]:
        """Return a hit/miss/size snapshot for every namespace."""
        result: dict[str, dict] = {}
        for name, ns in self._namespaces.items():
            with ns.lock:
                size = len(ns.store)
            snap: CacheStats = ns.metrics.snapshot(current_size=size)
            result[name] = snap.as_dict()
        return result


_manager_lock = threading.Lock()
_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Return the process-wide CacheManager singleton, creating it on first use."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = CacheManager()
    return _manager
