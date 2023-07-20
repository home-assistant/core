"""Interrupt context manager for asyncio.

This module provides a context manager that can be used to interrupt
a block of code when a future is done.

The purpose is to raise as soon as possible to avoid any race conditions.

This is based loosely on async_timeout by Andrew Svetlov and cpython asyncio.timeout
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from types import TracebackType
from typing import TYPE_CHECKING, Any, final

__version__ = "1.0.0"

__all__ = ("interrupt",)


@final
class _Interrupt:
    """Interrupt context manager.

    Internal class, please don't instantiate it directly
    Use interrupt() public factory instead.

    exception is raised immediately when future is finished.

    The purpose is to raise as soon as possible to avoid any race conditions.
    """

    __slots__ = (
        "_exception",
        "_future",
        "_exception_args",
        "_loop",
        "_interrupted",
        "_interrupt_call",
    )

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        future: asyncio.Future[Any],
        exception: type[Exception],
        exception_args: tuple[Any, ...] | None,
    ) -> None:
        """Initialize the interrupt context manager."""
        self._loop = loop
        self._future = future
        self._interrupted = False
        self._exception = exception
        self._exception_args = exception_args
        self._interrupt_call: Callable[[asyncio.Future[Any]], None] | None

    async def __aenter__(self) -> _Interrupt:
        """Enter the interrupt context manager."""
        task = asyncio.current_task()
        self._interrupt_call = partial(self._on_interrupt, task)
        self._future.add_done_callback(self._interrupt_call)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exit the interrupt context manager."""
        if exc_type is asyncio.CancelledError and self._interrupted:
            if self._exception_args is None:
                raise self._exception()
            raise self._exception(*self._exception_args)
        if TYPE_CHECKING:
            assert self._interrupt_call is not None
        self._future.remove_done_callback(self._interrupt_call)
        return None

    def _on_interrupt(self, task: asyncio.Task[Any], _: asyncio.Future[Any]) -> None:
        """Handle interrupt."""
        task.cancel("Interrupted by interrupt context manager")
        if TYPE_CHECKING:
            assert self._interrupt_call is not None
        self._future.remove_done_callback(self._interrupt_call)


def interrupt(
    future: asyncio.Future[Any],
    exception: type[Exception],
    exception_args: tuple[Any, ...] | None = None,
) -> _Interrupt:
    """Interrupt context manager.

    Useful in cases when you want to apply interrupt logic around block
    of code that uses await expression where an exception needs to be
    raised as soon as possible to avoid race conditions.

    >>> async with interrupt(future, APIUnavailableError, 'API is became unavailable'):
    ...     await api.call()


    future - the future that will cause the block to be interrupted
    exception - the exception to raise when the future is done
    exception_args - the arguments to pass to the exception constructor
    """
    loop = asyncio.get_running_loop()
    return _Interrupt(loop, future, exception, exception_args)
