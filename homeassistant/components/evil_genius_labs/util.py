"""Utilities for Evil Genius Labs."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, TypeVar

from typing_extensions import Concatenate, ParamSpec

from . import EvilGeniusEntity

_T = TypeVar("_T", bound=EvilGeniusEntity)
_R = TypeVar("_R")
_P = ParamSpec("_P")


def update_when_done(
    func: Callable[Concatenate[_T, _P], Awaitable[_R]]  # type: ignore[misc]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]]:  # type: ignore[misc]
    """Decorate function to trigger update when function is done."""

    @wraps(func)
    async def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Wrap function."""
        result = await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh()
        return result  # type: ignore[no-any-return]  # mypy can't yet infer 'func'

    return wrapper
