"""Decorator utility functions."""
import asyncio
from functools import wraps


class Registry(dict):
    """Registry of items."""

    def register(self, name):
        """Return decorator to register item with a specific name."""
        def decorator(func):
            """Register decorated function."""
            self[name] = func
            return func

        return decorator


def async_join_concurrent(method):
    """Decorator that will join concurrent calls.

    If a function is called while already being called from another task,
    the new caller will start awaiting the result of the call that is currently
    in progress.
    """
    progress = None

    @wraps(method)
    async def wrapper(*args, **kwargs):
        """Make parallel requests get the same answer."""
        nonlocal progress

        if progress is not None:
            return await progress

        progress = asyncio.ensure_future(method(*args, **kwargs))
        result = await progress
        progress = None
        return result

    return wrapper
