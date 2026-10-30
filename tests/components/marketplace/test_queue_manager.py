"""Tests for the Marketplace queue manager."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.marketplace.exceptions import ExecutionInProgressError
from homeassistant.components.marketplace.utils.queue_manager import QueueManager


async def test_queue_manager(caplog: pytest.LogCaptureFixture) -> None:
    """Test adding to and executing the queue."""
    task = AsyncMock()
    queue_manager = QueueManager()

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


async def test_queue_manager_already_running() -> None:
    """Test executing a queue that is already being executed."""
    queue_manager = QueueManager()
    queue_manager.running = True

    with pytest.raises(ExecutionInProgressError):
        await queue_manager.execute()


async def test_clear_during_execution() -> None:
    """Test clearing the queue while it runs, like an unload does, finishes cleanly."""
    queue_manager = QueueManager()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_task() -> None:
        started.set()
        await release.wait()

    queue_manager.add(slow_task())
    execution = asyncio.create_task(queue_manager.execute())
    await started.wait()

    queue_manager.clear()
    release.set()
    await execution

    assert not queue_manager.running
    assert not queue_manager.has_pending_tasks
