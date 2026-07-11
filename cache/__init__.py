"""vClinic in-process cache layer.

Public entry point: get_cache_manager() returns the process-wide CacheManager
singleton. Tool modules should not construct CacheManager directly.
"""

from cache.manager import CacheManager, get_cache_manager

__all__ = ["CacheManager", "get_cache_manager"]
