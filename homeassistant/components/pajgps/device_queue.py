"""
DeviceRequestQueue — serialises PAJ GPS API calls per device.

This is a pure asyncio concurrency primitive with no HA or network dependencies.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Any

from .const import REQUEST_DELAY

_LOGGER = logging.getLogger(__name__)


class DeviceRequestQueue:
    """
    Serialises PAJ GPS API calls for each device.

    Requests for different devices run fully in parallel; requests for the
    same device are queued and executed one-at-a-time with REQUEST_DELAY
    between them.  Duplicate job-type protection prevents the queue from
    filling up when the API responds slowly.
    """

    def __init__(self) -> None:
        # device_id → asyncio.Queue of (job_type, coro_factory, Future) triples
        self._queues: dict[int, asyncio.Queue] = {}
        # device_id → worker Task
        self._workers: dict[int, asyncio.Task] = {}
        # device_id → job_type currently being executed
        self._running: dict[int, str | None] = {}
        # device_id → set of job_types already waiting in the queue
        self._queued_types: dict[int, set[str]] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        device_id: int,
        job_type: str,
        coro_factory: Callable[[], Any],
    ) -> asyncio.Future:
        """
        Schedule coro_factory() on the queue for device_id.

        If a job with the same job_type is already queued or currently running
        for this device, returns a pre-resolved Future(None) immediately so
        callers can still await it safely without blocking.
        """
        self._ensure_device(device_id)

        # Duplicate-protection: skip if the same job type is already in-flight
        if job_type in self._queued_types[device_id] or self._running.get(device_id) == job_type:
            fut: asyncio.Future = asyncio.get_event_loop().create_future()
            fut.set_result(None)
            return fut

        fut = asyncio.get_event_loop().create_future()
        self._queued_types[device_id].add(job_type)
        await self._queues[device_id].put((job_type, coro_factory, fut))
        return fut

    async def shutdown(self) -> None:
        """Cancel all worker tasks and drain queues."""
        for task in self._workers.values():
            task.cancel()
        results = await asyncio.gather(*self._workers.values(), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                _LOGGER.debug("DeviceRequestQueue worker error during shutdown: %s", result)
        self._workers.clear()
        self._queues.clear()
        self._running.clear()
        self._queued_types.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_device(self, device_id: int) -> None:
        """Create queue and worker for device_id if they do not exist yet."""
        if device_id not in self._queues:
            self._queues[device_id] = asyncio.Queue()
            self._running[device_id] = None
            self._queued_types[device_id] = set()
            self._workers[device_id] = asyncio.ensure_future(
                self._worker(device_id)
            )

    async def _worker(self, device_id: int) -> None:
        """Consume jobs from this device's queue indefinitely."""
        while True:
            job_type, coro_factory, fut = await self._queues[device_id].get()
            self._running[device_id] = job_type
            self._queued_types[device_id].discard(job_type)
            try:
                result = await coro_factory()
                if not fut.done():
                    fut.set_result(result)
            except Exception as exc:  # noqa: BLE001
                if not fut.done():
                    fut.set_exception(exc)
            finally:
                self._running[device_id] = None
                self._queues[device_id].task_done()
                # Honor the minimum inter-request delay before taking the next job
                await asyncio.sleep(REQUEST_DELAY)
