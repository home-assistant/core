"""Tests for async util methods from Python source."""

import contextlib
import importlib
from pathlib import Path, PurePosixPath
import time
from typing import Any
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


async def test_protect_loop_open(caplog: pytest.LogCaptureFixture) -> None:
    """Test open of a file in /proc is not reported."""
    block_async_io.enable()
    with contextlib.suppress(FileNotFoundError):
        open("/proc/does_not_exist").close()
    assert "Detected blocking call to open with args" not in caplog.text


async def test_protect_open(caplog: pytest.LogCaptureFixture) -> None:
    """Test opening a file in the event loop logs."""
    block_async_io.enable()
    with contextlib.suppress(FileNotFoundError):
        open("/config/data_not_exist").close()

    assert "Detected blocking call to open with args" in caplog.text


@pytest.mark.parametrize(
    "path",
    [
        "/config/data_not_exist",
        Path("/config/data_not_exist"),
        PurePosixPath("/config/data_not_exist"),
    ],
)
async def test_protect_open_path(path: Any, caplog: pytest.LogCaptureFixture) -> None:
    """Test opening a file by path in the event loop logs."""
    block_async_io.enable()
    with contextlib.suppress(FileNotFoundError):
        open(path).close()

    assert "Detected blocking call to open with args" in caplog.text
