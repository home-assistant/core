"""Decorators for the Marketplace."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any


def concurrent[**P, T](
    concurrenttasks: int,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Limit how many calls of the decorated function run at the same time."""

    max_concurrent = asyncio.Semaphore(concurrenttasks)

    def inner_function(
        function: Callable[P, Awaitable[T]],
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async with max_concurrent:
                return await function(*args, **kwargs)

        return wrapper

    return inner_function


def return_none_on_exception[**P, T](
    func: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, Coroutine[Any, Any, T | None]]:
    """Return None instead of raising, for anything the call runs into."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
        try:
            return await func(*args, **kwargs)
        except Exception:  # noqa: BLE001 # the decorator exists to swallow anything
            return None

    return wrapper
