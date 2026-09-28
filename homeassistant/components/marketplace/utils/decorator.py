"""Decorators for the Marketplace."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import inspect
from typing import Any, overload

from ..const import DEFAULT_CONCURRENT_TASKS


def concurrent[**P, T](
    concurrenttasks: int = DEFAULT_CONCURRENT_TASKS,
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


@overload
def return_none_on_exception[**P, T](
    func: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, Coroutine[Any, Any, T | None]]: ...


@overload
def return_none_on_exception[**P, T](
    func: Callable[P, T],
) -> Callable[P, T | None]: ...


def return_none_on_exception(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to return None on any exception, works for sync/async, methods/functions."""

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception:  # noqa: BLE001 # the decorator exists to swallow anything
            return None

    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception:  # noqa: BLE001 # the decorator exists to swallow anything
            return None

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
