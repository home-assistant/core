"""Tests for the Community store queue manager."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.store.exceptions import ExecutionInProgressError
from homeassistant.components.store.utils.queue_manager import QueueManager
from homeassistant.core import HomeAssistant


async def test_queue_manager(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test adding to and executing the queue."""
    task = AsyncMock()
    queue_manager = QueueManager(hass=hass)

    assert not queue_manager.running
    assert not queue_manager.has_pending_tasks
    assert queue_manager.pending_tasks == 0

    for _ in range(5):
        queue_manager.add(task())

    assert queue_manager.has_pending_tasks
    assert queue_manager.pending_tasks == 5

    await queue_manager.execute(1)
    assert queue_manager.pending_tasks == 4

    await queue_manager.execute()
    assert not queue_manager.running
    assert not queue_manager.has_pending_tasks

    await queue_manager.execute()
    assert "The queue is empty" in caplog.text


async def test_queue_manager_already_running(hass: HomeAssistant) -> None:
    """Test executing a queue that is already being executed."""
    queue_manager = QueueManager(hass=hass)
    queue_manager.running = True

    with pytest.raises(ExecutionInProgressError):
        await queue_manager.execute()
