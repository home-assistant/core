"""Tests for async util methods from Python source."""
import asyncio
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant import block_async_io
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


def banned_function():
    """Mock banned function."""


async def test_check_loop_async() -> None:
    """Test check_loop detects when called from event loop without integration context."""
    with pytest.raises(RuntimeError):
        hasync.check_loop(banned_function)


async def test_check_loop_async_integration(caplog: pytest.LogCaptureFixture) -> None:
    """Test check_loop detects and raises when called from event loop from integration context."""
    with pytest.raises(RuntimeError), patch(
        "homeassistant.helpers.frame.extract_stack",
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
        hasync.check_loop(banned_function)
    assert (
        "Detected blocking call to banned_function inside the event loop by integration"
        " 'hue' at homeassistant/components/hue/light.py, line 23: self.light.is_on, "
        "please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22" in caplog.text
    )


async def test_check_loop_async_integration_non_strict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test check_loop detects when called from event loop from integration context."""
    with patch(
        "homeassistant.helpers.frame.extract_stack",
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
        hasync.check_loop(banned_function, strict=False)
    assert (
        "Detected blocking call to banned_function inside the event loop by integration"
        " 'hue' at homeassistant/components/hue/light.py, line 23: self.light.is_on, "
        "please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22" in caplog.text
    )


async def test_check_loop_async_custom(caplog: pytest.LogCaptureFixture) -> None:
    """Test check_loop detects when called from event loop with custom component context."""
    with pytest.raises(RuntimeError), patch(
        "homeassistant.helpers.frame.extract_stack",
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
        hasync.check_loop(banned_function)
    assert (
        "Detected blocking call to banned_function inside the event loop by custom "
        "integration 'hue' at custom_components/hue/light.py, line 23: self.light.is_on"
        ", please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text


def test_check_loop_sync(caplog: pytest.LogCaptureFixture) -> None:
    """Test check_loop does nothing when called from thread."""
    hasync.check_loop(banned_function)
    assert "Detected blocking call inside the event loop" not in caplog.text


def test_protect_loop_sync() -> None:
    """Test protect_loop calls check_loop."""
    func = Mock()
    with patch("homeassistant.util.async_.check_loop") as mock_check_loop:
        hasync.protect_loop(func)(1, test=2)
    mock_check_loop.assert_called_once_with(func, strict=True)
    func.assert_called_once_with(1, test=2)


async def test_protect_loop_debugger_sleep(caplog: pytest.LogCaptureFixture) -> None:
    """Test time.sleep injected by the debugger is not reported."""
    block_async_io.enable()

    with patch(
        "homeassistant.util.async_.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/.venv/blah/pydevd.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/homeassistant/util/async.py",
                lineno="123",
                line="protected_loop_func",
            ),
            Mock(
                filename="/home/paulus/homeassistant/util/async.py",
                lineno="123",
                line="check_loop()",
            ),
        ],
    ):
        time.sleep(0)
    assert "Detected blocking call inside the event loop" not in caplog.text


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

    with patch.object(
        hass.loop, "call_soon_threadsafe"
    ) as mock_call_soon_threadsafe, pytest.raises(RuntimeError):
        hasync.run_callback_threadsafe(hass.loop, callback)

    mock_call_soon_threadsafe.assert_called_once()
