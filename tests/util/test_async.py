"""Tests for async util methods from Python source."""

import asyncio
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util import async_ as hasync


@patch("concurrent.futures.Future")
@patch("threading.get_ident")
def test_run_callback_threadsafe_from_inside_event_loop(mock_ident, _) -> None:
    """Testing calling run_callback_threadsafe from inside an event loop."""
    callback = MagicMock()

    loop = Mock(spec=["call_soon_threadsafe"])

    loop._thread_ident = None
    mock_ident.return_value = 5
    hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 5
    mock_ident.return_value = 5
    with pytest.raises(RuntimeError):
        hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 2


async def test_gather_with_limited_concurrency() -> None:
    """Test gather_with_limited_concurrency limits the number of running tasks."""

    runs = 0
    now_time = time.time()

    async def _increment_runs_if_in_time():
        if time.time() - now_time > 0.1:
            return -1

        nonlocal runs
        runs += 1
        await asyncio.sleep(0.1)
        return runs

    results = await hasync.gather_with_limited_concurrency(
        2, *(_increment_runs_if_in_time() for i in range(4))
    )

    assert results == [2, 2, -1, -1]


async def test_shutdown_run_callback_threadsafe(hass: HomeAssistant) -> None:
    """Test we can shutdown run_callback_threadsafe."""
    hasync.shutdown_run_callback_threadsafe(hass.loop)
    callback = MagicMock()

    with pytest.raises(RuntimeError):
        hasync.run_callback_threadsafe(hass.loop, callback)


async def test_run_callback_threadsafe(hass: HomeAssistant) -> None:
    """Test run_callback_threadsafe runs code in the event loop."""
    it_ran = False

    def callback():
        nonlocal it_ran
        it_ran = True

    assert hasync.run_callback_threadsafe(hass.loop, callback)
    assert it_ran is False

    # Verify that async_block_till_done will flush
    # out the callback
    await hass.async_block_till_done()
    assert it_ran is True


async def test_callback_is_always_scheduled(hass: HomeAssistant) -> None:
    """Test run_callback_threadsafe always calls call_soon_threadsafe before checking for shutdown."""
    # We have to check the shutdown state AFTER the callback is scheduled otherwise
    # the function could continue on and the caller call `future.result()` after
    # the point in the main thread where callbacks are no longer run.

    callback = MagicMock()
    hasync.shutdown_run_callback_threadsafe(hass.loop)

    with (
        patch.object(hass.loop, "call_soon_threadsafe") as mock_call_soon_threadsafe,
        pytest.raises(RuntimeError),
    ):
        hasync.run_callback_threadsafe(hass.loop, callback)

    mock_call_soon_threadsafe.assert_called_once()


async def test_create_eager_task_312(hass: HomeAssistant) -> None:
    """Test create_eager_task schedules a task eagerly in the event loop.

    For Python 3.12+, the task is scheduled eagerly in the event loop.
    """
    events = []

    async def _normal_task():
        events.append("normal")

    async def _eager_task():
        events.append("eager")

    task1 = hasync.create_eager_task(_eager_task())
    task2 = asyncio.create_task(_normal_task())

    assert events == ["eager"]

    await asyncio.sleep(0)
    assert events == ["eager", "normal"]
    await task1
    await task2
