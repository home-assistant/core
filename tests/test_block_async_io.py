"""Tests for async util methods from Python source."""

import importlib
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


async def test_protect_loop_sleep_get_current_frame_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test time.sleep when get_current_frame raises ValueError."""
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
            side_effect=ValueError,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        time.sleep(0)


async def test_protect_loop_importlib_import_module_non_integration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_module in the loop for non-loaded module."""
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
        pytest.raises(ImportError),
        patch.object(block_async_io, "_IN_TESTS", False),
        patch(
            "homeassistant.block_async_io.get_current_frame",
            return_value=frames,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        block_async_io.enable()
        importlib.import_module("not_loaded_module")

    assert "Detected blocking call to import_module" in caplog.text


async def test_protect_loop_importlib_import_loaded_module_non_integration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_module in the loop for a loaded module."""
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
        patch.object(block_async_io, "_IN_TESTS", False),
        patch(
            "homeassistant.block_async_io.get_current_frame",
            return_value=frames,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        block_async_io.enable()
        importlib.import_module("sys")

    assert "Detected blocking call to import_module" not in caplog.text


async def test_protect_loop_importlib_import_module_in_integration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_module in the loop for non-loaded module in an integration."""
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
        pytest.raises(ImportError),
        patch.object(block_async_io, "_IN_TESTS", False),
        patch(
            "homeassistant.block_async_io.get_current_frame",
            return_value=frames,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        block_async_io.enable()
        importlib.import_module("not_loaded_module")

    assert (
        "Detected blocking call to import_module inside the event loop by "
        "integration 'hue' at homeassistant/components/hue/light.py, line 23"
    ) in caplog.text
