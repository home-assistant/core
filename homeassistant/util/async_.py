"""Asyncio backports for Python 3.6 compatibility."""
import concurrent.futures
import threading
import logging
from asyncio import coroutines
from asyncio.events import AbstractEventLoop

import asyncio
from asyncio import ensure_future
from typing import Any, Coroutine, Callable, TypeVar, Awaitable

_LOGGER = logging.getLogger(__name__)


try:
    # pylint: disable=invalid-name
    asyncio_run = asyncio.run  # type: ignore
except AttributeError:
    _T = TypeVar("_T")

    def asyncio_run(main: Awaitable[_T], *, debug: bool = False) -> _T:
        """Minimal re-implementation of asyncio.run (since 3.7)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(debug)
        try:
            return loop.run_until_complete(main)
        finally:
            asyncio.set_event_loop(None)
            loop.close()


def fire_coroutine_threadsafe(coro: Coroutine, loop: AbstractEventLoop) -> None:
    """Submit a coroutine object to a given event loop.

    This method does not provide a way to retrieve the result and
    is intended for fire-and-forget use. This reduces the
    work involved to fire the function on the loop.
    """
    ident = loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError("Cannot be called from within the event loop")

    if not coroutines.iscoroutine(coro):
        raise TypeError("A coroutine object is required: %s" % coro)

    def callback() -> None:
        """Handle the firing of a coroutine."""
        ensure_future(coro, loop=loop)

    loop.call_soon_threadsafe(callback)


def run_callback_threadsafe(
    loop: AbstractEventLoop, callback: Callable, *args: Any
) -> concurrent.futures.Future:
    """Submit a callback object to a given event loop.

    Return a concurrent.futures.Future to access the result.
    """
    ident = loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError("Cannot be called from within the event loop")

    future: concurrent.futures.Future = concurrent.futures.Future()

    def run_callback() -> None:
        """Run callback and store result."""
        try:
            future.set_result(callback(*args))
        except Exception as exc:  # pylint: disable=broad-except
            if future.set_running_or_notify_cancel():
                future.set_exception(exc)
            else:
                _LOGGER.warning("Exception on lost future: ", exc_info=True)

    loop.call_soon_threadsafe(run_callback)
    return future
