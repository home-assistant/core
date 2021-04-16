"""Executor util helpers."""

from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import sys
import traceback

from homeassistant.util.thread import async_raise

_LOGGER = logging.getLogger(__name__)

_JOIN_ATTEMPTS = 10

START_LOG_ATTEMPT = 2


def _log_thread_running_at_shutdown(name: str, ident: int) -> None:
    """Log the stack of a thread that was still running at shutdown."""

    frames = sys._current_frames()
    stack = frames.get(ident)
    formatted_stack = traceback.format_stack(stack)
    _LOGGER.warning(
        "Thread[%s] is still running at shutdown: %s",
        name,
        "".join(formatted_stack).strip(),
    )


class InterruptibleThreadPoolExecutor(ThreadPoolExecutor):
    """A ThreadPoolExecutor instance that will not deadlock on shutdown."""

    def logged_shutdown(self) -> None:
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

        remaining_threads = list(self._threads)  # type: ignore[attr-defined]

        for attempt in range(1, _JOIN_ATTEMPTS + 1):
            joined = []

            for thread in remaining_threads:
                thread.join(timeout=0.1)
                ident = thread.ident
                if not thread.is_alive() or ident is None:
                    joined.append(thread)
                    continue

                if attempt >= START_LOG_ATTEMPT:
                    _log_thread_running_at_shutdown(thread.name, ident)

                async_raise(ident, SystemExit)
                thread.join(timeout=1)

            for thread in joined:
                remaining_threads.remove(thread)

            if not remaining_threads:
                return
