"""Utilities for Evil Genius Labs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from . import EvilGeniusEntity


def update_when_done[_EvilGeniusEntityT: EvilGeniusEntity, **_P, _R](
    func: Callable[Concatenate[_EvilGeniusEntityT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_EvilGeniusEntityT, _P], Coroutine[Any, Any, _R]]:
    """Decorate function to trigger update when function is done."""

    @wraps(func)
    async def wrapper(
        self: _EvilGeniusEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        """Wrap function."""
        result = await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh()
        return result

    return wrapper
