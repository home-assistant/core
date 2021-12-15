"""Tests for async util methods from Python source."""
import asyncio
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.util import async_ as hasync


@patch("asyncio.coroutines.iscoroutine")
@patch("concurrent.futures.Future")
@patch("threading.get_ident")
def test_fire_coroutine_threadsafe_from_inside_event_loop(
    mock_ident, _, mock_iscoroutine
):
    """Testing calling fire_coroutine_threadsafe from inside an event loop."""
    coro = MagicMock()
    loop = MagicMock()

    loop._thread_ident = None
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 5
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    with pytest.raises(RuntimeError):
        hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = False
    with pytest.raises(TypeError):
        hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 1

    loop._thread_ident = 1
    mock_ident.return_value = 5
    mock_iscoroutine.return_value = True
    hasync.fire_coroutine_threadsafe(coro, loop)
    assert len(loop.call_soon_threadsafe.mock_calls) == 2


@patch("concurrent.futures.Future")
@patch("threading.get_ident")
def test_run_callback_threadsafe_from_inside_event_loop(mock_ident, _):
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


async def test_check_loop_async():
    """Test check_loop detects when called from event loop without integration context."""
    with pytest.raises(RuntimeError):
        hasync.check_loop()


async def test_check_loop_async_integration(caplog):
    """Test check_loop detects when called from event loop from integration context."""
    with pytest.raises(RuntimeError), patch(
        "homeassistant.util.async_.extract_stack",
        return_value=[
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
        ],
    ):
        hasync.check_loop()
    assert (
        "Detected I/O inside the event loop. This is causing stability issues. Please report issue for hue doing I/O at homeassistant/components/hue/light.py, line 23: self.light.is_on"
        in caplog.text
    )


async def test_check_loop_async_custom(caplog):
    """Test check_loop detects when called from event loop with custom component context."""
    with pytest.raises(RuntimeError), patch(
        "homeassistant.util.async_.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/config/custom_components/hue/light.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        hasync.check_loop()
    assert (
        "Detected I/O inside the event loop. This is causing stability issues. Please report issue to the custom component author for hue doing I/O at custom_components/hue/light.py, line 23: self.light.is_on"
        in caplog.text
    )


def test_check_loop_sync(caplog):
    """Test check_loop does nothing when called from thread."""
    hasync.check_loop()
    assert "Detected I/O inside the event loop" not in caplog.text


def test_protect_loop_sync():
    """Test protect_loop calls check_loop."""
    calls = []
    with patch("homeassistant.util.async_.check_loop") as mock_loop:
        hasync.protect_loop(calls.append)(1)
    assert len(mock_loop.mock_calls) == 1
    assert calls == [1]


async def test_gather_with_concurrency():
    """Test gather_with_concurrency limits the number of running tasks."""

    runs = 0
    now_time = time.time()

    async def _increment_runs_if_in_time():
        if time.time() - now_time > 0.1:
            return -1

        nonlocal runs
        runs += 1
        await asyncio.sleep(0.1)
        return runs

    results = await hasync.gather_with_concurrency(
        2, *(_increment_runs_if_in_time() for i in range(4))
    )

    assert results == [2, 2, -1, -1]


async def test_shutdown_run_callback_threadsafe(hass):
    """Test we can shutdown run_callback_threadsafe."""
    hasync.shutdown_run_callback_threadsafe(hass.loop)
    callback = MagicMock()

    with pytest.raises(RuntimeError):
        hasync.run_callback_threadsafe(hass.loop, callback)


async def test_run_callback_threadsafe(hass):
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


async def test_callback_is_always_scheduled(hass):
    """Test run_callback_threadsafe always calls call_soon_threadsafe before checking for shutdown."""
    # We have to check the shutdown state AFTER the callback is scheduled otherwise
    # the function could continue on and the caller call `future.result()` after
    # the point in the main thread where callbacks are no longer run.

    callback = MagicMock()
    hasync.shutdown_run_callback_threadsafe(hass.loop)

    with patch.object(
        hass.loop, "call_soon_threadsafe"
    ) as mock_call_soon_threadsafe, pytest.raises(RuntimeError):
        hasync.run_callback_threadsafe(hass.loop, callback)

    mock_call_soon_threadsafe.assert_called_once()
