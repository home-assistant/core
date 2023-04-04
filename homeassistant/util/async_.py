"""Asyncio utilities."""
from __future__ import annotations

from asyncio import Semaphore, gather, get_running_loop
from asyncio.events import AbstractEventLoop
from collections.abc import Awaitable, Callable
import concurrent.futures
import functools
import logging
import threading
from traceback import extract_stack
from typing import Any, ParamSpec, TypeVar

_LOGGER = logging.getLogger(__name__)

_SHUTDOWN_RUN_CALLBACK_THREADSAFE = "_shutdown_run_callback_threadsafe"

_T = TypeVar("_T")
_R = TypeVar("_R")
_P = ParamSpec("_P")


def run_callback_threadsafe(
    loop: AbstractEventLoop, callback: Callable[..., _T], *args: Any
) -> concurrent.futures.Future[_T]:
    """Submit a callback object to a given event loop.

    Return a concurrent.futures.Future to access the result.
    """
    ident = loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError("Cannot be called from within the event loop")

    future: concurrent.futures.Future[_T] = concurrent.futures.Future()

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

    if hasattr(loop, _SHUTDOWN_RUN_CALLBACK_THREADSAFE):
        #
        # If the final `HomeAssistant.async_block_till_done` in
        # `HomeAssistant.async_stop` has already been called, the callback
        # will never run and, `future.result()` will block forever which
        # will prevent the thread running this code from shutting down which
        # will result in a deadlock when the main thread attempts to shutdown
        # the executor and `.join()` the thread running this code.
        #
        # To prevent this deadlock we do the following on shutdown:
        #
        # 1. Set the _SHUTDOWN_RUN_CALLBACK_THREADSAFE attr on this function
        #    by calling `shutdown_run_callback_threadsafe`
        # 2. Call `hass.async_block_till_done` at least once after shutdown
        #    to ensure all callbacks have run
        # 3. Raise an exception here to ensure `future.result()` can never be
        #    called and hit the deadlock since once `shutdown_run_callback_threadsafe`
        #    we cannot promise the callback will be executed.
        #
        raise RuntimeError("The event loop is in the process of shutting down.")

    return future


def check_loop(
    func: Callable[..., Any], strict: bool = True, advise_msg: str | None = None
) -> None:
    """Warn if called inside the event loop. Raise if `strict` is True.

    The default advisory message is 'Use `await hass.async_add_executor_job()'
    Set `advise_msg` to an alternate message if the solution differs.
    """
    try:
        get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        return

    found_frame = None

    stack = extract_stack()

    if (
        func.__name__ == "sleep"
        and len(stack) >= 3
        and stack[-3].filename.endswith("pydevd.py")
    ):
        # Don't report `time.sleep` injected by the debugger (pydevd.py)
        # stack[-1] is us, stack[-2] is protected_loop_func, stack[-3] is the offender
        return

    for frame in reversed(stack):
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
            f"Detected blocking call to {func.__name__} inside the event loop. "
            f"{advise_msg or 'Use `await hass.async_add_executor_job()`'}; "
            "This is causing stability issues. Please report issue"
        )

    start = index + len(path)
    end = found_frame.filename.index("/", start)

    integration = found_frame.filename[start:end]

    if path == "custom_components/":
        extra = " to the custom integration author"
    else:
        extra = ""

    _LOGGER.warning(
        (
            "Detected blocking call to %s inside the event loop. This is causing"
            " stability issues. Please report issue%s for %s doing blocking calls at"
            " %s, line %s: %s"
        ),
        func.__name__,
        extra,
        integration,
        found_frame.filename[index:],
        found_frame.lineno,
        (found_frame.line or "?").strip(),
    )
    if strict:
        raise RuntimeError(
            "Blocking calls must be done in the executor or a separate thread;"
            f" {advise_msg or 'Use `await hass.async_add_executor_job()`'}; at"
            f" {found_frame.filename[index:]}, line {found_frame.lineno}:"
            f" {(found_frame.line or '?').strip()}"
        )


def protect_loop(func: Callable[_P, _R], strict: bool = True) -> Callable[_P, _R]:
    """Protect function from running in event loop."""

    @functools.wraps(func)
    def protected_loop_func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        check_loop(func, strict=strict)
        return func(*args, **kwargs)

    return protected_loop_func


async def gather_with_concurrency(
    limit: int, *tasks: Any, return_exceptions: bool = False
) -> Any:
    """Wrap asyncio.gather to limit the number of concurrent tasks.

    From: https://stackoverflow.com/a/61478547/9127614
    """
    semaphore = Semaphore(limit)

    async def sem_task(task: Awaitable[Any]) -> Any:
        async with semaphore:
            return await task

    return await gather(
        *(sem_task(task) for task in tasks), return_exceptions=return_exceptions
    )


def shutdown_run_callback_threadsafe(loop: AbstractEventLoop) -> None:
    """Call when run_callback_threadsafe should prevent creating new futures.

    We must finish all callbacks before the executor is shutdown
    or we can end up in a deadlock state where:

    `executor.result()` is waiting for its `._condition`
    and the executor shutdown is trying to `.join()` the
    executor thread.

    This function is considered irreversible and should only ever
    be called when Home Assistant is going to shutdown and
    python is going to exit.
    """
    setattr(loop, _SHUTDOWN_RUN_CALLBACK_THREADSAFE, True)
