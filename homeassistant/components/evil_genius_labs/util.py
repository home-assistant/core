"""Utilities for Evil Genius Labs."""
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from . import EvilGeniusEntity

CallableT = TypeVar("CallableT", bound=Callable)


def update_when_done(func: CallableT) -> CallableT:
    """Decorate function to trigger update when function is done."""

    @wraps(func)
    async def wrapper(self: EvilGeniusEntity, *args: Any, **kwargs: Any) -> Any:
        """Wrap function."""
        result = await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh()
        return result

    return cast(CallableT, wrapper)
