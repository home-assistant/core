"""The QueueManager class."""

import asyncio
from collections.abc import Coroutine
import inspect
import time
from typing import Any

from homeassistant.core import HomeAssistant

from ..exceptions import ExecutionInProgressError
from .logger import LOGGER

_LOGGER = LOGGER


class QueueManager:
    """The QueueManager class."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the queue manager."""
        self.hass = hass
        self.queue: list[Coroutine[Any, Any, Any]] = []
        self.running = False

    @property
    def pending_tasks(self) -> int:
        """Return a count of pending tasks in the queue."""
        return len(self.queue)

    @property
    def has_pending_tasks(self) -> bool:
        """Return a count of pending tasks in the queue."""
        return self.pending_tasks != 0

    def clear(self) -> None:
        """Clear the queue, the tasks that did not start never will."""
        for task in self.queue:
            if inspect.getcoroutinestate(task) == inspect.CORO_CREATED:
                task.close()
        self.queue = []

    def add(self, task: Coroutine[Any, Any, Any]) -> None:
        """Add a task to the queue."""
        self.queue.append(task)

    async def execute(self, number_of_tasks: int | None = None) -> None:
        """Execute the tasks in the queue."""
        if self.running:
            _LOGGER.debug("<QueueManager> Execution is already running")
            raise ExecutionInProgressError
        if len(self.queue) == 0:
            _LOGGER.debug("<QueueManager> The queue is empty")
            return

        self.running = True
        try:
            await self._async_execute(number_of_tasks)
        finally:
            self.running = False

    async def _async_execute(self, number_of_tasks: int | None) -> None:
        """Execute a number of the tasks in the queue."""
        _LOGGER.debug("<QueueManager> Checking out tasks to execute")
        local_queue = list(
            self.queue[:number_of_tasks] if number_of_tasks else self.queue
        )

        _LOGGER.debug(
            "<QueueManager> Starting queue execution for %s tasks", len(local_queue)
        )
        start = time.time()
        result = await asyncio.gather(*local_queue, return_exceptions=True)
        for entry in result:
            if isinstance(entry, Exception):
                _LOGGER.error("<QueueManager> %s", entry)
        end = time.time() - start

        # A clear while they ran already emptied the queue
        for task in local_queue:
            if task in self.queue:
                self.queue.remove(task)

        _LOGGER.debug(
            "<QueueManager> Queue execution finished for %s tasks finished in %.2f seconds",
            len(local_queue),
            end,
        )
        if self.has_pending_tasks:
            _LOGGER.debug(
                "<QueueManager> %s tasks remaining in the queue", len(self.queue)
            )
