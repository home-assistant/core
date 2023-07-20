"""Interrupt context manager for asyncio.

This module provides a context manager that can be used to interrupt
a block of code when a future is done.

The purpose is to raise as soon as possible to avoid any race conditions.

This is based loosely on async_timeout by Andrew Svetlov and cpython asyncio.timeout
"""
from __future__ import annotations

import asyncio
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
        "_message",
        "_loop",
        "_interrupted",
        "_task",
        "_cancelling",
        "_exited",
    )

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        future: asyncio.Future[Any],
        exception: type[Exception],
        message: str | None,
    ) -> None:
        """Initialize the interrupt context manager."""
        self._loop = loop
        self._future = future
        self._interrupted = False
        self._exception = exception
        self._message = message
        self._task: asyncio.Task | None
        self._cancelling: int = 0
        self._exited = False

    async def __aenter__(self) -> _Interrupt:
        """Enter the interrupt context manager."""
        if self._exited:
            raise RuntimeError("Already exited")
        task = asyncio.current_task()
        self._task = task
        if cancelling := getattr(task, "cancelling", None):
            self._cancelling = cancelling()
        self._future.add_done_callback(self._on_interrupt)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exit the interrupt context manager."""
        self._exited = True
        if self._interrupted:
            if TYPE_CHECKING:
                assert self._task is not None
            if exc_type is asyncio.CancelledError and (
                not (uncancel := getattr(self._task, "uncancel", None))
                or uncancel() <= self._cancelling
            ):
                # Only py3.11 has uncancel, but this is OK since
                # if there really is multiple cancel requests
                # it will raise on the next loop anyways
                if self._message:
                    raise self._exception(self._message) from exc_val
                raise self._exception from exc_val
        self._future.remove_done_callback(self._on_interrupt)
        return None

    def _on_interrupt(self, _: asyncio.Future[Any]) -> None:
        """Handle interrupt."""
        if self._exited:
            # Must not cancel the task here if we already
            # exited the context manager or the cancellation
            # would raise upwards
            return
        if TYPE_CHECKING:
            assert self._task is not None
        self._interrupted = True
        self._task.cancel("Interrupted by interrupt context manager")
        self._future.remove_done_callback(self._on_interrupt)


def interrupt(
    future: asyncio.Future[Any],
    exception: type[Exception],
    message: str | None,
) -> _Interrupt:
    """Interrupt context manager.

    Useful in cases when you want to apply interrupt logic around block
    of code that uses await expression where an exception needs to be
    raised as soon as possible to avoid race conditions.

    >>> async with interrupt(future, APIUnavailableError, 'API is became unavailable'):
    ...     await api.call()


    future - the future that will cause the block to be interrupted
    exception - the exception to raise when the future is done
    message - the message to pass when constructing the exception
    """
    loop = asyncio.get_running_loop()
    return _Interrupt(loop, future, exception, message)
