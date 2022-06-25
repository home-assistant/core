"""Utilities for Evil Genius Labs."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, TypeVar

from typing_extensions import Concatenate, ParamSpec

from . import EvilGeniusEntity

_EvilGeniusEntityT = TypeVar("_EvilGeniusEntityT", bound=EvilGeniusEntity)
_R = TypeVar("_R")
_P = ParamSpec("_P")


def update_when_done(
    func: Callable[Concatenate[_EvilGeniusEntityT, _P], Awaitable[_R]]
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
