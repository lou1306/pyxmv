import os
from collections.abc import Callable
from functools import _make_key, lru_cache, wraps

sentinel = object()
PathLike = str | os.PathLike


def fifo_cache(maxsize: int | None | Callable = 128):
    """Cache that evicts the "earliest" entry.

    This implementation relies on the fact that Python dictionaries are ordered
    (this is true since Python 3.6).
    """
    if maxsize is None:
        """Just return the infinity cache"""
        return lru_cache(maxsize=None)
    elif isinstance(maxsize, int):
        # Negative maxsize is treated as 0 (as in lru_cache)
        if maxsize < 0:
            maxsize = 0
    elif callable(maxsize):
        # This allows us to use @fifo_cache without parentheses
        return fifo_cache(128)(maxsize)
    else:
        raise TypeError('Expected first argument to be an integer or None')
    cache: dict = {}

    def pseudo_fifo_cache_inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = _make_key(args, kwargs, True)
            result = cache.get(key, sentinel)
            if result is not sentinel:
                return result
            result = func(*args, **kwargs)
            if len(cache) == maxsize:
                del cache[next(iter(cache))]
            cache[key] = result
            return result
        return wrapper
    return pseudo_fifo_cache_inner
