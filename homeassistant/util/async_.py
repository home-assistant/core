"""Asyncio utilities."""

from __future__ import annotations

from asyncio import AbstractEventLoop, Future, Semaphore, Task, gather, get_running_loop
from collections.abc import Awaitable, Callable, Coroutine
import concurrent.futures
import logging
import threading
from typing import Any, TypeVar, TypeVarTuple

_LOGGER = logging.getLogger(__name__)

_SHUTDOWN_RUN_CALLBACK_THREADSAFE = "_shutdown_run_callback_threadsafe"

_T = TypeVar("_T")
_Ts = TypeVarTuple("_Ts")


def create_eager_task(
    coro: Coroutine[Any, Any, _T],
    *,
    name: str | None = None,
    loop: AbstractEventLoop | None = None,
) -> Task[_T]:
    """Create a task from a coroutine and schedule it to run immediately."""
    if not loop:
        try:
            loop = get_running_loop()
        except RuntimeError:
            # If there is no running loop, create_eager_task is being called from
            # the wrong thread.
            # Late import to avoid circular dependencies
            # pylint: disable-next=import-outside-toplevel
            from homeassistant.helpers import frame

            frame.report("attempted to create an asyncio task from a thread")
            raise

    return Task(coro, loop=loop, name=name, eager_start=True)


def cancelling(task: Future[Any]) -> bool:
    """Return True if task is cancelling."""
    return bool((cancelling_ := getattr(task, "cancelling", None)) and cancelling_())


def run_callback_threadsafe(
    loop: AbstractEventLoop, callback: Callable[[*_Ts], _T], *args: *_Ts
) -> concurrent.futures.Future[_T]:
    """Submit a callback object to a given event loop.

    Return a concurrent.futures.Future to access the result.
    """
    if (ident := loop.__dict__.get("_thread_ident")) and ident == threading.get_ident():
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


async def gather_with_limited_concurrency(
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
        *(create_eager_task(sem_task(task)) for task in tasks),
        return_exceptions=return_exceptions,
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
