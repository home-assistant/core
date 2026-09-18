"""Decorators for the Community store."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import inspect
from typing import TYPE_CHECKING, Any, overload

from ..const import DEFAULT_CONCURRENT_BACKOFF_TIME, DEFAULT_CONCURRENT_TASKS

if TYPE_CHECKING:
    from ..base import StoreManager


def concurrent[**P, T](
    concurrenttasks: int = DEFAULT_CONCURRENT_TASKS,
    backoff_time: float = DEFAULT_CONCURRENT_BACKOFF_TIME,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Return a modified function."""

    max_concurrent = asyncio.Semaphore(concurrenttasks)

    def inner_function(
        function: Callable[P, Awaitable[T]],
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            store: StoreManager | None = getattr(args[0], "store", None)

            async with max_concurrent:
                result = await function(*args, **kwargs)
                if (
                    store is None
                    or store.queue is None
                    or store.queue.has_pending_tasks
                    or "update" not in function.__name__
                ):
                    await asyncio.sleep(backoff_time)

                return result

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
