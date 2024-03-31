"""Tests for async util methods from Python source."""

import time
from unittest.mock import Mock, patch

import pytest

from homeassistant import block_async_io

from tests.common import extract_stack_to_frame


async def test_protect_loop_debugger_sleep(caplog: pytest.LogCaptureFixture) -> None:
    """Test time.sleep injected by the debugger is not reported."""
    block_async_io.enable()
    frames = extract_stack_to_frame(
        [
            Mock(
                filename="/home/paulus/homeassistant/.venv/blah/pydevd.py",
                lineno="23",
                line="do_something()",
            ),
        ]
    )
    with (
        patch(
            "homeassistant.block_async_io.get_current_frame",
            return_value=frames,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        time.sleep(0)
    assert "Detected blocking call inside the event loop" not in caplog.text


async def test_protect_loop_sleep(caplog: pytest.LogCaptureFixture) -> None:
    """Test time.sleep not injected by the debugger raises."""
    block_async_io.enable()
    frames = extract_stack_to_frame(
        [
            Mock(
                filename="/home/paulus/homeassistant/no_dev.py",
                lineno="23",
                line="do_something()",
            ),
        ]
    )
    with (
        pytest.raises(
            RuntimeError, match="Detected blocking call to sleep inside the event loop"
        ),
        patch(
            "homeassistant.block_async_io.get_current_frame",
            return_value=frames,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        time.sleep(0)
