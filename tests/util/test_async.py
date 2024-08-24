"""Tests for async util methods from Python source."""

import asyncio
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util import async_ as hasync

from tests.common import extract_stack_to_frame


@patch("concurrent.futures.Future")
@patch("threading.get_ident")
def test_run_callback_threadsafe_from_inside_event_loop(
    mock_ident: MagicMock, mock_future: MagicMock
) -> None:
    """Testing calling run_callback_threadsafe from inside an event loop."""
    callback = MagicMock()

    loop = Mock(spec=["call_soon_threadsafe"])

    loop._thread_id = None
    mock_ident.return_value = 5
    hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_id = 5
    mock_ident.return_value = 5
    with pytest.raises(RuntimeError):
        hasync.run_callback_threadsafe(loop, callback)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_id = 1
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

    with patch.dict(hass.loop.__dict__, {"_thread_id": -1}):
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
        patch.dict(hass.loop.__dict__, {"_thread_id": -1}),
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


async def test_create_eager_task_from_thread(hass: HomeAssistant) -> None:
    """Test we report trying to create an eager task from a thread."""

    def create_task():
        hasync.create_eager_task(asyncio.sleep(0))

    with pytest.raises(
        RuntimeError,
        match=(
            "Detected code that attempted to create an asyncio task from a thread. Please report this issue."
        ),
    ):
        await hass.async_add_executor_job(create_task)


async def test_create_eager_task_from_thread_in_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we report trying to create an eager task from a thread."""

    def create_task():
        hasync.create_eager_task(asyncio.sleep(0))

    frames = extract_stack_to_frame(
        [
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/homeassistant/components/hue/light.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ]
    )
    with (
        pytest.raises(RuntimeError, match="no running event loop"),
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="self.light.is_on",
        ),
        patch(
            "homeassistant.util.loop._get_line_from_cache",
            return_value="mock_line",
        ),
        patch(
            "homeassistant.util.loop.get_current_frame",
            return_value=frames,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        await hass.async_add_executor_job(create_task)

    assert (
        "Detected that integration 'hue' attempted to create an asyncio task "
        "from a thread at homeassistant/components/hue/light.py, line 23: "
        "self.light.is_on"
    ) in caplog.text


async def test_get_scheduled_timer_handles(hass: HomeAssistant) -> None:
    """Test get_scheduled_timer_handles returns all scheduled timer handles."""
    loop = hass.loop
    timer_handle = loop.call_later(10, lambda: None)
    timer_handle2 = loop.call_later(5, lambda: None)
    timer_handle3 = loop.call_later(15, lambda: None)

    handles = hasync.get_scheduled_timer_handles(loop)
    assert set(handles).issuperset({timer_handle, timer_handle2, timer_handle3})
    timer_handle.cancel()
    timer_handle2.cancel()
    timer_handle3.cancel()
