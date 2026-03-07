"""Tests for DeviceRequestQueue: serialisation, duplicate protection, parallel execution across devices, error propagation, and shutdown."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.pajgps.coordinator import DeviceRequestQueue


async def test_single_job_executed() -> None:
    """Test that a single enqueued job is executed."""
    queue = DeviceRequestQueue()
    called: list[int] = []
    fut = await queue.enqueue(
        1,
        "sensor",
        AsyncMock(return_value="ok", side_effect=lambda: called.append(1) or "ok"),
    )
    await asyncio.wait_for(fut, timeout=2)
    assert 1 in called
    await queue.shutdown()


async def test_result_returned_via_future() -> None:
    """Test that the future returned by enqueue resolves to the job result."""
    queue = DeviceRequestQueue()
    fut = await queue.enqueue(1, "sensor", AsyncMock(return_value="result"))
    result = await asyncio.wait_for(fut, timeout=2)
    assert result == "result"
    await queue.shutdown()


async def test_duplicate_job_skipped() -> None:
    """Enqueueing the same job_type twice should execute it only once."""
    queue = DeviceRequestQueue()
    call_count = 0

    async def slow_job() -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return "done"

    fut1 = await queue.enqueue(1, "sensor", slow_job)
    fut2 = await queue.enqueue(1, "sensor", slow_job)  # duplicate — should be skipped

    r1 = await asyncio.wait_for(fut1, timeout=2)
    r2 = await asyncio.wait_for(fut2, timeout=2)

    assert r1 == "done"
    assert r2 is None  # pre-resolved with None
    assert call_count == 1
    await queue.shutdown()


async def test_different_job_types_both_execute() -> None:
    """Test that different job types for the same device both execute."""
    queue = DeviceRequestQueue()

    fut1 = await queue.enqueue(1, "sensor", AsyncMock(return_value="sensor_result"))
    fut2 = await queue.enqueue(
        1, "notifications", AsyncMock(return_value="notif_result")
    )

    r1 = await asyncio.wait_for(fut1, timeout=2)
    r2 = await asyncio.wait_for(fut2, timeout=2)

    assert r1 == "sensor_result"
    assert r2 == "notif_result"
    await queue.shutdown()


async def test_different_devices_run_in_parallel() -> None:
    """Jobs for device 1 and device 2 should not block each other."""
    queue = DeviceRequestQueue()
    start_times: dict[int, float] = {}
    end_times: dict[int, float] = {}

    async def timed_job(device_id: int) -> int:
        start_times[device_id] = time.monotonic()
        await asyncio.sleep(0.1)
        end_times[device_id] = time.monotonic()
        return device_id

    fut1 = await queue.enqueue(1, "sensor", lambda: timed_job(1))
    fut2 = await queue.enqueue(2, "sensor", lambda: timed_job(2))

    await asyncio.gather(
        asyncio.wait_for(fut1, timeout=2),
        asyncio.wait_for(fut2, timeout=2),
    )

    # Both should have started before either finished (parallel)
    overlap = start_times[2] < end_times[1] and start_times[1] < end_times[2]
    assert overlap, "Jobs for different devices should run in parallel"
    await queue.shutdown()


async def test_exception_propagates_via_future() -> None:
    """Test that exceptions raised in a job are propagated through the future."""
    queue = DeviceRequestQueue()

    async def failing_job() -> None:
        raise ValueError("boom")

    fut = await queue.enqueue(1, "sensor", failing_job)
    with pytest.raises(ValueError):
        await asyncio.wait_for(fut, timeout=2)
    await queue.shutdown()


async def test_shutdown_cancels_workers() -> None:
    """Test that shutdown cancels all active workers."""
    queue = DeviceRequestQueue()
    # Ensure a worker is created
    fut = await queue.enqueue(1, "sensor", AsyncMock(return_value=None))
    await asyncio.wait_for(fut, timeout=2)
    await queue.shutdown()
    assert len(queue._workers) == 0
