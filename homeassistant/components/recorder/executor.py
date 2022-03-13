"""Database executor helpers."""
from __future__ import annotations

from concurrent.futures.thread import _threads_queues, _worker
import threading
from typing import Any
import weakref

from homeassistant.util.executor import InterruptibleThreadPoolExecutor


def _worker_with_shutdown_hook(shutdown, *args, **kwargs):
    """Create a worker that calls a function after its finished."""
    _worker(*args, **kwargs)
    shutdown()


class DBInterruptibleThreadPoolExecutor(InterruptibleThreadPoolExecutor):
    """A database instance that will not deadlock on shutdown."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init the executor."""
        self._shutdown = kwargs.pop("shutdown")
        super().__init__(*args, **kwargs)

    def _adjust_thread_count(self) -> None:
        # if idle threads are available, don't spin new threads
        if self._idle_semaphore.acquire(  # pylint: disable=consider-using-with
            timeout=0
        ):
            return

        # When the executor gets lost, the weakref callback will wake up
        # the worker threads.
        def weakref_cb(_, q=self._work_queue):  # pylint: disable=invalid-name
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = "%s_%d" % (self._thread_name_prefix or self, num_threads)
            executor_thread = threading.Thread(
                name=thread_name,
                target=_worker_with_shutdown_hook,
                args=(
                    self._shutdown,
                    weakref.ref(self, weakref_cb),
                    self._work_queue,
                    self._initializer,
                    self._initargs,
                ),
            )
            executor_thread.start()
            self._threads.add(executor_thread)  # type: ignore[attr-defined]
            _threads_queues[executor_thread] = self._work_queue  # type: ignore[index]
