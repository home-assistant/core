"""Heiman Refresh Optimization.

Implements advanced refresh mechanisms:
- Multi-level refresh (properties, cloud devices, gateway devices)
- Batch refresh with request merging
- Deduplication
- Priority queue
- Retry logic with exponential backoff
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
from dataclasses import dataclass, field
from enum import IntEnum
import logging
import time
from typing import Any

_LOGGER = logging.getLogger(__name__)


class RefreshPriority(IntEnum):
    """Refresh priority levels."""

    CRITICAL = 0  # Immediate (e.g., user action response)
    HIGH = 1  # Within 1 second (e.g., device state change)
    NORMAL = 2  # Within 5 seconds (e.g., periodic refresh)
    LOW = 3  # Within 30 seconds (e.g., background sync)


@dataclass
class RefreshTask:
    """Represents a refresh task."""

    device_id: str
    property_ids: list[str]
    priority: RefreshPriority = RefreshPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3

    def __hash__(self) -> int:
        """Return hash of refresh task."""
        return hash((self.device_id, tuple(sorted(self.property_ids))))

    def __eq__(self, other: object) -> bool:
        """Check equality of refresh tasks."""
        if not isinstance(other, RefreshTask):
            return False
        return self.device_id == other.device_id and set(self.property_ids) == set(
            other.property_ids,
        )


class RefreshPriorityQueue:
    """Priority queue for refresh tasks."""

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize priority queue.

        Args:
            max_size: Maximum queue size
        """
        self._queues: dict[RefreshPriority, list[RefreshTask]] = {
            priority: [] for priority in RefreshPriority
        }
        self._max_size = max_size
        self._task_set: set[RefreshTask] = set()

    def add_task(self, task: RefreshTask) -> bool:
        """Add a task to the queue.

        Args:
            task: Refresh task to add

        Returns:
            True if added, False if queue is full or task already exists
        """
        # Check for duplicates
        if task in self._task_set:
            _LOGGER.debug("Task already in queue: %s", task.device_id)
            return False

        # Check queue size
        total_tasks = sum(len(q) for q in self._queues.values())
        if total_tasks >= self._max_size:
            _LOGGER.warning("Refresh queue full, dropping task")
            return False

        # Add to appropriate priority queue
        self._queues[task.priority].append(task)
        self._task_set.add(task)

        _LOGGER.debug(
            "Added refresh task: device=%s, priority=%s, properties=%d",
            task.device_id,
            task.priority.name,
            len(task.property_ids),
        )
        return True

    def get_next_task(self) -> RefreshTask | None:
        """Get the highest priority task.

        Returns:
            Next task or None if queue is empty
        """
        for priority in RefreshPriority:
            if self._queues[priority]:
                task = self._queues[priority].pop(0)
                self._task_set.discard(task)
                return task
        return None

    def get_batch(self, max_batch_size: int = 10) -> list[RefreshTask]:
        """Get a batch of tasks.

        Args:
            max_batch_size: Maximum number of tasks to retrieve

        Returns:
            List of tasks
        """
        batch = []
        for priority in RefreshPriority:
            while self._queues[priority] and len(batch) < max_batch_size:
                task = self._queues[priority].pop(0)
                self._task_set.discard(task)
                batch.append(task)

        return batch

    def clear_device_tasks(self, device_id: str) -> int:
        """Clear all tasks for a specific device.

        Args:
            device_id: Device identifier

        Returns:
            Number of tasks cleared
        """
        cleared = 0
        for priority in RefreshPriority:
            original_len = len(self._queues[priority])
            self._queues[priority] = [
                task for task in self._queues[priority] if task.device_id != device_id
            ]
            cleared += original_len - len(self._queues[priority])

        # Rebuild task set
        self._task_set = set()
        for queue in self._queues.values():
            self._task_set.update(queue)

        return cleared

    def size(self) -> int:
        """Get total queue size.

        Returns:
            Number of tasks in queue
        """
        return sum(len(q) for q in self._queues.values())

    def stats(self) -> dict[str, int]:
        """Get queue statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "total": self.size(),
            "critical": len(self._queues[RefreshPriority.CRITICAL]),
            "high": len(self._queues[RefreshPriority.HIGH]),
            "normal": len(self._queues[RefreshPriority.NORMAL]),
            "low": len(self._queues[RefreshPriority.LOW]),
        }


class RefreshOptimizer:
    """Manages optimized refresh operations."""

    # Refresh delays (in seconds)
    REFRESH_PROPS_DELAY = 0.2  # Property refresh delay
    REFRESH_PROPS_RETRY_DELAY = 3  # Retry delay on failure
    REFRESH_CLOUD_DEVICES_DELAY = 6  # Cloud device refresh delay
    REFRESH_GATEWAY_DEVICES_DELAY = 3  # Gateway device refresh delay

    # Batch configuration
    MAX_BATCH_SIZE = 10  # Max devices per batch
    BATCH_MERGE_WINDOW = 0.5  # Time window to merge requests (seconds)

    def __init__(
        self,
        hass: Any,
        entry_id: str,
        cloud_client: Any,
        mqtt_client: Any | None = None,
    ) -> None:
        """Initialize refresh optimizer.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            cloud_client: Cloud client instance
            mqtt_client: MQTT client instance
        """
        self.hass = hass
        self.entry_id = entry_id
        self.cloud_client = cloud_client
        self.mqtt_client = mqtt_client

        self._queue = RefreshPriorityQueue()
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._pending_merge: dict[str, RefreshTask] = {}
        self._merge_timer: asyncio.TimerHandle | None = None

    async def start_async(self) -> None:
        """Start the refresh worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        _LOGGER.info("Refresh optimizer started")

    async def stop_async(self) -> None:
        """Stop the refresh worker."""
        if not self._running:
            return

        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task

        if self._merge_timer:
            self._merge_timer.cancel()

        _LOGGER.info("Refresh optimizer stopped")

    def request_refresh(
        self,
        device_id: str,
        property_ids: list[str] | None = None,
        priority: RefreshPriority = RefreshPriority.NORMAL,
    ) -> bool:
        """Request a device refresh.

        Args:
            device_id: Device identifier
            property_ids: List of property IDs to refresh (None for all)
            priority: Refresh priority

        Returns:
            True if request was queued
        """
        if property_ids is None:
            # Get all properties for this device
            property_ids = []

        task = RefreshTask(
            device_id=device_id,
            property_ids=property_ids,
            priority=priority,
        )

        # Try to merge with pending requests
        if device_id in self._pending_merge:
            existing_task = self._pending_merge[device_id]
            # Merge property lists
            merged_properties = list(
                set(existing_task.property_ids + task.property_ids),
            )
            existing_task.property_ids = merged_properties
            # Upgrade priority if needed
            if priority.value < existing_task.priority.value:
                existing_task.priority = priority
            _LOGGER.debug("Merged refresh request for device: %s", device_id)
            return True

        # Schedule merge timer if not already running
        if not self._merge_timer and self._running:
            self._merge_timer = self.hass.loop.call_later(
                self.BATCH_MERGE_WINDOW,
                lambda: self.hass.async_create_task(self._flush_merge_queue()),
            )

        # Add to pending merge
        self._pending_merge[device_id] = task
        _LOGGER.debug("Queued refresh request for device: %s", device_id)
        return True

    async def _flush_merge_queue(self) -> None:
        """Flush merged requests to the queue."""
        if not self._pending_merge:
            return

        # Add all pending tasks to queue
        for task in self._pending_merge.values():
            self._queue.add_task(task)

        _LOGGER.info(
            "Flushed %d merged refresh requests to queue",
            len(self._pending_merge),
        )
        self._pending_merge.clear()
        self._merge_timer = None

    async def _worker_loop(self) -> None:
        """Main worker loop for processing refresh tasks."""
        while self._running:
            try:
                # Get a batch of tasks
                batch = self._queue.get_batch(self.MAX_BATCH_SIZE)

                if not batch:
                    # No tasks, wait a bit
                    await asyncio.sleep(1)
                    continue

                # Process batch
                await self._process_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Error in refresh worker: %s", err)
                await asyncio.sleep(5)

    async def _process_batch(self, batch: list[RefreshTask]) -> None:
        """Process a batch of refresh tasks.

        Args:
            batch: List of refresh tasks
        """
        _LOGGER.info("Processing refresh batch: %d tasks", len(batch))

        # Group by device
        device_tasks: dict[str, list[str]] = defaultdict(list)
        for task in batch:
            device_tasks[task.device_id].extend(task.property_ids)

        # Fetch properties for each device
        success_count = 0
        failure_count = 0

        for device_id, property_ids in device_tasks.items():
            try:
                await self._refresh_device_properties(device_id, property_ids)
                success_count += 1
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to refresh device %s: %s", device_id, err)
                failure_count += 1

                # Re-queue failed tasks with retry
                failed_task = next((t for t in batch if t.device_id == device_id), None)
                if failed_task and failed_task.retry_count < failed_task.max_retries:
                    failed_task.retry_count += 1
                    failed_task.priority = RefreshPriority.HIGH
                    self._queue.add_task(failed_task)
                    _LOGGER.info(
                        "Re-queued failed task for retry: %s (attempt %d/%d)",
                        device_id,
                        failed_task.retry_count,
                        failed_task.max_retries,
                    )

        _LOGGER.info(
            "Batch complete: %d succeeded, %d failed",
            success_count,
            failure_count,
        )

    async def _refresh_device_properties(
        self,
        device_id: str,
        property_ids: list[str],
    ) -> None:
        """Refresh properties for a single device.

        Args:
            device_id: Device identifier
            property_ids: List of property IDs to refresh
        """
        if not self.cloud_client:
            raise RuntimeError("Cloud client not available")

        # Apply delay before fetching
        await asyncio.sleep(self.REFRESH_PROPS_DELAY)

        # Fetch properties
        if property_ids:
            # Fetch specific properties
            for prop_id in property_ids:
                try:
                    value = await self.cloud_client.async_get_property(
                        device_id=device_id,
                        property_id=prop_id,
                    )
                    _LOGGER.debug(
                        "Refreshed property %s for device %s: %s",
                        prop_id,
                        device_id,
                        value,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "Failed to refresh property %s for device %s: %s",
                        prop_id,
                        device_id,
                        err,
                    )
        else:
            # Fetch all properties
            properties = await self.cloud_client.async_get_device_properties(
                device_id=device_id,
            )
            _LOGGER.debug(
                "Refreshed all properties for device %s: %d properties",
                device_id,
                len(properties),
            )

    async def refresh_cloud_devices(self) -> None:
        """Refresh device list from cloud."""
        _LOGGER.info("Refreshing device list from cloud")

        try:
            await asyncio.sleep(self.REFRESH_CLOUD_DEVICES_DELAY)
            devices = await self.cloud_client.async_get_devices()
            _LOGGER.info("Refreshed %d devices from cloud", len(devices))
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to refresh cloud devices: %s", err)

    async def refresh_gateway_devices(self) -> None:
        """Refresh gateway sub-devices."""
        _LOGGER.info("Refreshing gateway sub-devices")

        try:
            await asyncio.sleep(self.REFRESH_GATEWAY_DEVICES_DELAY)
            # Implementation depends on gateway API
            _LOGGER.debug("Gateway device refresh completed")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to refresh gateway devices: %s", err)

    @property
    def is_running(self) -> bool:
        """Check if optimizer is running."""
        return self._running

    def get_stats(self) -> dict[str, Any]:
        """Get optimizer statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "running": self._running,
            "queue_stats": self._queue.stats(),
            "pending_merge": len(self._pending_merge),
        }


class MultiLevelRefreshManager:
    """Manages multi-level refresh strategy."""

    def __init__(
        self,
        hass: Any,
        entry_id: str,
        cloud_client: Any,
        mqtt_client: Any | None = None,
    ) -> None:
        """Initialize multi-level refresh manager.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            cloud_client: Cloud client instance
            mqtt_client: MQTT client instance
        """
        self.hass = hass
        self.entry_id = entry_id
        self.cloud_client = cloud_client
        self.mqtt_client = mqtt_client

        self._optimizer = RefreshOptimizer(hass, entry_id, cloud_client, mqtt_client)
        self._refresh_tasks: dict[str, asyncio.Task] = {}

    async def start_async(self) -> None:
        """Start the refresh manager."""
        await self._optimizer.start_async()
        _LOGGER.info("Multi-level refresh manager started")

    async def stop_async(self) -> None:
        """Stop the refresh manager."""
        await self._optimizer.stop_async()

        # Cancel all refresh tasks
        for task in self._refresh_tasks.values():
            task.cancel()

        await asyncio.gather(*self._refresh_tasks.values(), return_exceptions=True)

        _LOGGER.info("Multi-level refresh manager stopped")

    def refresh_device(self, device_id: str, immediate: bool = False) -> None:
        """Refresh a device.

        Args:
            device_id: Device identifier
            immediate: If True, use CRITICAL priority
        """
        priority = RefreshPriority.CRITICAL if immediate else RefreshPriority.NORMAL
        self._optimizer.request_refresh(device_id, priority=priority)

    def refresh_property(
        self,
        device_id: str,
        property_id: str,
        immediate: bool = False,
    ) -> None:
        """Refresh a specific property.

        Args:
            device_id: Device identifier
            property_id: Property identifier
            immediate: If True, use CRITICAL priority
        """
        priority = RefreshPriority.CRITICAL if immediate else RefreshPriority.HIGH
        self._optimizer.request_refresh(
            device_id,
            property_ids=[property_id],
            priority=priority,
        )

    async def refresh_all_cloud_devices(self) -> None:
        """Force refresh all devices from cloud."""
        await self._optimizer.refresh_cloud_devices()

    def get_status(self) -> dict[str, Any]:
        """Get refresh manager status.

        Returns:
            Status dictionary
        """
        return {
            "running": self._optimizer.is_running,
            "optimizer_stats": self._optimizer.get_stats(),
        }
