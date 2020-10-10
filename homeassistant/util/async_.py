"""Asyncio backports for Python 3.6 compatibility."""
from asyncio import coroutines, ensure_future, get_running_loop
from asyncio.events import AbstractEventLoop
import concurrent.futures
import functools
import logging
import threading
from traceback import extract_stack
from typing import Any, Callable, Coroutine, TypeVar

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


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
    loop: AbstractEventLoop, callback: Callable[..., T], *args: Any
) -> "concurrent.futures.Future[T]":
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


def check_loop() -> None:
    """Warn if called inside the event loop."""
    try:
        get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        return

    found_frame = None

    for frame in reversed(extract_stack()):
        for path in ("custom_components/", "homeassistant/components/"):
            try:
                index = frame.filename.index(path)
                found_frame = frame
                break
            except ValueError:
                continue

        if found_frame is not None:
            break

    # Did not source from integration? Hard error.
    if found_frame is None:
        raise RuntimeError(
            "Detected I/O inside the event loop. This is causing stability issues. Please report issue"
        )

    start = index + len(path)
    end = found_frame.filename.index("/", start)

    integration = found_frame.filename[start:end]

    if path == "custom_components/":
        extra = " to the custom component author"
    else:
        extra = ""

    _LOGGER.warning(
        "Detected I/O inside the event loop. This is causing stability issues. Please report issue%s for %s doing I/O at %s, line %s: %s",
        extra,
        integration,
        found_frame.filename[index:],
        found_frame.lineno,
        found_frame.line.strip(),
    )


def protect_loop(func: Callable) -> Callable:
    """Protect function from running in event loop."""

    @functools.wraps(func)
    def protected_loop_func(*args, **kwargs):  # type: ignore
        check_loop()
        return func(*args, **kwargs)

    return protected_loop_func
