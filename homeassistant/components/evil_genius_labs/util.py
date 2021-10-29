"""Utilities for Evil Genius Labs."""
from functools import wraps


def update_when_done(func):
    """Decorate function to trigger update when function is done."""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        """Wrap function."""
        result = await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh()
        return result

    return wrapper
