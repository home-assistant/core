"""Executor util helpers."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextlib
import logging
import queue
import sys
from threading import Thread
import time
import traceback

from homeassistant.util.thread import async_raise

_LOGGER = logging.getLogger(__name__)

MAX_LOG_ATTEMPTS = 2

_JOIN_ATTEMPTS = 10

EXECUTOR_SHUTDOWN_TIMEOUT = 10


def _log_thread_running_at_shutdown(name: str, ident: int) -> None:
    """Log the stack of a thread that was still running at shutdown."""
    frames = sys._current_frames()  # pylint: disable=protected-access
    stack = frames.get(ident)
    formatted_stack = traceback.format_stack(stack)
    _LOGGER.warning(
        "Thread[%s] is still running at shutdown: %s",
        name,
        "".join(formatted_stack).strip(),
    )


def join_or_interrupt_threads(
    threads: set[Thread], timeout: float, log: bool
) -> set[Thread]:
    """Attempt to join or interrupt a set of threads."""
    joined = set()
    timeout_per_thread = timeout / len(threads)

    for thread in threads:
        thread.join(timeout=timeout_per_thread)

        if not thread.is_alive() or thread.ident is None:
            joined.add(thread)
            continue

        if log:
            _log_thread_running_at_shutdown(thread.name, thread.ident)

        with contextlib.suppress(SystemError):
            # SystemError at this stage is usually a race condition
            # where the thread happens to die right before we force
            # it to raise the exception
            async_raise(thread.ident, SystemExit)

    return joined


class InterruptibleThreadPoolExecutor(ThreadPoolExecutor):
    """A ThreadPoolExecutor instance that will not deadlock on shutdown."""

    def shutdown(self, *args, **kwargs) -> None:  # type: ignore
        """Shutdown backport from cpython 3.9 with interrupt support added."""
        with self._shutdown_lock:  # type: ignore[attr-defined]
            self._shutdown = True
            # Drain all work items from the queue, and then cancel their
            # associated futures.
            while True:
                try:
                    work_item = self._work_queue.get_nowait()
                except queue.Empty:
                    break
                if work_item is not None:
                    work_item.future.cancel()
            # Send a wake-up to prevent threads calling
            # _work_queue.get(block=True) from permanently blocking.
            self._work_queue.put(None)

        # The above code is backported from python 3.9
        #
        # For maintainability join_threads_or_timeout is
        # a separate function since it is not a backport from
        # cpython itself
        #
        self.join_threads_or_timeout()

    def join_threads_or_timeout(self) -> None:
        """Join threads or timeout."""
        remaining_threads = set(self._threads)  # type: ignore[attr-defined]
        start_time = time.monotonic()
        timeout_remaining: float = EXECUTOR_SHUTDOWN_TIMEOUT
        attempt = 0

        while True:
            if not remaining_threads:
                return

            attempt += 1

            remaining_threads -= join_or_interrupt_threads(
                remaining_threads,
                timeout_remaining / _JOIN_ATTEMPTS,
                attempt <= MAX_LOG_ATTEMPTS,
            )

            timeout_remaining = EXECUTOR_SHUTDOWN_TIMEOUT - (
                time.monotonic() - start_time
            )
            if timeout_remaining <= 0:
                return
