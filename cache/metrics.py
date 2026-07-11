"""Thread-safe hit/miss/eviction counters, one set per cache namespace."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    current_size: int = 0
    max_size: int = 0
    ttl_s: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def as_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "current_size": self.current_size,
            "max_size": self.max_size,
            "ttl_s": self.ttl_s,
        }


class NamespaceMetrics:
    """Hit/miss counters for a single namespace. Guarded by the caller's lock."""

    def __init__(self, maxsize: int, ttl: int) -> None:
        self._hits = 0
        self._misses = 0
        self.maxsize = maxsize
        self.ttl = ttl
        self._lock = threading.Lock()

    def record_hit(self) -> None:
        with self._lock:
            self._hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self._misses += 1

    def snapshot(self, current_size: int) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                current_size=current_size,
                max_size=self.maxsize,
                ttl_s=self.ttl,
            )
