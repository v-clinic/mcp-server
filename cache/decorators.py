"""Cache decorators applied to tool read/write functions.

@cached       — wraps a read function. Checks the cache first; on miss calls
                the wrapped function, stores the result, and returns it. Cache
                lookups never raise; a cache-layer problem always falls back
                to hitting the database.

@invalidates  — wraps a write function. Invalidation runs only after the
                wrapped function returns successfully (no invalidation on
                exception, since nothing was committed).

Every cache lookup (hit or miss) is recorded to the audit log via
audit_logger.log_cache_event, satisfying the requirement that cache
hit/miss be auditable.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Optional

from cache.manager import get_cache_manager


def _bound_kwargs(fn: Callable, args: tuple, kwargs: dict) -> dict:
    """Bind positional+keyword call args to parameter names, applying defaults.

    This lets key_fn callables always receive named arguments regardless of
    whether the caller used positional or keyword form.
    """
    sig = inspect.signature(fn)
    bound = sig.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _always_cache(_result: Any) -> bool:
    return True


def cached(namespace: str, key_fn: Callable[..., str], should_cache: Callable[[Any], bool] = _always_cache):
    """Decorator for read functions.

    key_fn is called with the bound call arguments as keyword arguments and
    must return a cache key string.

    should_cache is called with the function's return value; return False to
    skip storing it (e.g. to avoid caching an error payload returned by a
    function that reports failures as data rather than exceptions).
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Import here (not at module scope) to avoid a hard import-time
            # dependency cycle between audit_logger and cache.
            from audit_logger import log_cache_event

            manager = get_cache_manager()
            bound = _bound_kwargs(fn, args, kwargs)
            key = key_fn(**bound)

            cached_value = manager.get(namespace, key)
            hit = cached_value is not None
            log_cache_event(fn.__name__, namespace, key, hit=hit)
            if hit:
                return cached_value

            result = fn(*args, **kwargs)
            if should_cache(result):
                manager.set(namespace, key, result)
            return result

        return wrapper
    return decorator


# Each rule is (namespace, key_fn). key_fn=None means "flush the whole
# namespace" — used when the parent identifier needed for a precise key
# isn't available among the write function's own arguments.
InvalidationRule = tuple[str, Optional[Callable[..., str]]]


def invalidates(rules: list[InvalidationRule]):
    """Decorator for write functions. Invalidates cache entries after success."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)  # let exceptions propagate untouched

            manager = get_cache_manager()
            bound = _bound_kwargs(fn, args, kwargs)
            for namespace, key_fn in rules:
                if key_fn is None:
                    manager.flush_namespace(namespace)
                else:
                    key = key_fn(**bound)
                    manager.invalidate(namespace, key)

            return result

        return wrapper
    return decorator
