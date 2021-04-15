"""Executor util helpers."""

from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import sys
from threading import Thread
import traceback

from homeassistant.util.thread import async_raise

_LOGGER = logging.getLogger(__name__)


def _log_thread_running_at_shutdown(name: str, ident: int) -> None:
    """Log the stack of a thread that was still running at shutdown."""

    frames = sys._current_frames()
    stack = frames.get(ident)
    formatted_stack = traceback.format_stack(stack)
    _LOGGER.critical(
        "Thread[%s] was still running at shutdown: %s",
        name,
        "".join(formatted_stack),
    )


def _join_or_interrupt_thread(thread: Thread) -> None:
    """Join or interrupt a thread."""
    _LOGGER.critical("Thread[%s]: attempting join", thread.name)
    thread.join(timeout=1)
    ident = thread.ident
    _LOGGER.critical("Thread[%s]: did join", thread.name)
    if not thread.is_alive() or ident is None:
        return
    _log_thread_running_at_shutdown(thread.name, ident)
    async_raise(ident, KeyboardInterrupt)
    thread.join(timeout=5)
    if thread.is_alive():
        _LOGGER.critical(
            "Thread[%s]: failed to interrupt and was left running", thread.name
        )


class InterruptibleThreadPoolExecutor(ThreadPoolExecutor):
    """A ThreadPoolExecutor instance that will not deadlock on shutdown."""

    def shutdown(
        self,
        wait: bool = True,
        *,
        cancel_futures: bool = False,
        interrupt: bool = False,
    ) -> None:
        """Shutdown backport from cpython 3.9 with interrupt support added."""
        with self._shutdown_lock:  # type: ignore[attr-defined]
            self._shutdown = True
            if cancel_futures:
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
        if wait:
            for t in self._threads:  # type: ignore[attr-defined]
                if interrupt:
                    _join_or_interrupt_thread(t)
                else:
                    t.join()
