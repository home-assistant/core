"""Database executor helpers."""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures.thread import _threads_queues, _worker
import threading
from typing import Any
import weakref

from homeassistant.util.executor import InterruptibleThreadPoolExecutor


def _worker_with_shutdown_hook(
    shutdown_hook: Callable[[], None], *args: Any, **kwargs: Any
) -> None:
    """Create a worker that calls a function after its finished."""
    _worker(*args, **kwargs)
    shutdown_hook()


class DBInterruptibleThreadPoolExecutor(InterruptibleThreadPoolExecutor):
    """A database instance that will not deadlock on shutdown."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init the executor with a shutdown hook support."""
        self._shutdown_hook: Callable[[], None] = kwargs.pop("shutdown_hook")
        super().__init__(*args, **kwargs)

    def _adjust_thread_count(self) -> None:
        """Overridden to add support for shutdown hook.

        Based on the CPython 3.10 implementation.
        """
        # if idle threads are available, don't spin new threads
        if self._idle_semaphore.acquire(  # pylint: disable=consider-using-with
            timeout=0
        ):
            return

        # When the executor gets lost, the weakref callback will wake up
        # the worker threads.
        # pylint: disable=invalid-name
        def weakref_cb(  # type: ignore[no-untyped-def]
            _: Any,
            q=self._work_queue,
        ) -> None:
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = "%s_%d" % (self._thread_name_prefix or self, num_threads)
            executor_thread = threading.Thread(
                name=thread_name,
                target=_worker_with_shutdown_hook,
                args=(
                    self._shutdown_hook,
                    weakref.ref(self, weakref_cb),
                    self._work_queue,
                    self._initializer,
                    self._initargs,
                ),
            )
            executor_thread.start()
            self._threads.add(executor_thread)  # type: ignore[attr-defined]
            _threads_queues[executor_thread] = self._work_queue  # type: ignore[index]
