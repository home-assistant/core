"""Tests for async util methods from Python source."""

import contextlib
import glob
import importlib
import os
from pathlib import Path, PurePosixPath
import ssl
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant import block_async_io
from homeassistant.core import HomeAssistant

from .common import extract_stack_to_frame


@pytest.fixture(autouse=True)
def disable_block_async_io(disable_block_async_io):
    """Disable the loop protection from block_async_io after each test."""


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
        time.sleep(0)  # noqa: ASYNC251
    assert "Detected blocking call inside the event loop" not in caplog.text


async def test_protect_loop_sleep() -> None:
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
        pytest.raises(RuntimeError, match="Caught blocking call to sleep with args"),
        patch(
            "homeassistant.block_async_io.get_current_frame",
            return_value=frames,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        time.sleep(0)  # noqa: ASYNC251


async def test_protect_loop_sleep_get_current_frame_raises() -> None:
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
        pytest.raises(RuntimeError, match="Caught blocking call to sleep with args"),
        patch(
            "homeassistant.block_async_io.get_current_frame",
            side_effect=ValueError,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
    ):
        time.sleep(0)  # noqa: ASYNC251


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
        with pytest.raises(ImportError):
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
        with pytest.raises(ImportError):
            importlib.import_module("not_loaded_module")

    assert (
        "Detected blocking call to import_module with args ('not_loaded_module',) "
        "inside the event loop by "
        "integration 'hue' at homeassistant/components/hue/light.py, line 23"
    ) in caplog.text


async def test_protect_loop_open(caplog: pytest.LogCaptureFixture) -> None:
    """Test open of a file in /proc is not reported."""
    block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        open("/proc/does_not_exist", encoding="utf8"),  # noqa: ASYNC230
    ):
        pass
    assert "Detected blocking call to open with args" not in caplog.text


async def test_protect_loop_path_open(caplog: pytest.LogCaptureFixture) -> None:
    """Test opening a file in /proc is not reported."""
    block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        Path("/proc/does_not_exist").open(encoding="utf8"),  # noqa: ASYNC230
    ):
        pass
    assert "Detected blocking call to open with args" not in caplog.text


async def test_protect_open(caplog: pytest.LogCaptureFixture) -> None:
    """Test opening a file in the event loop logs."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        open("/config/data_not_exist", encoding="utf8"),  # noqa: ASYNC230
    ):
        pass

    assert "Detected blocking call to open with args" in caplog.text


async def test_protect_path_open(caplog: pytest.LogCaptureFixture) -> None:
    """Test opening a file in the event loop logs."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        Path("/config/data_not_exist").open(encoding="utf8"),  # noqa: ASYNC230
    ):
        pass

    assert "Detected blocking call to open with args" in caplog.text


async def test_protect_path_read_bytes(caplog: pytest.LogCaptureFixture) -> None:
    """Test reading file bytes in the event loop logs."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        Path("/config/data_not_exist").read_bytes(),  # noqa: ASYNC230
    ):
        pass

    assert "Detected blocking call to read_bytes with args" in caplog.text


async def test_protect_path_read_text(caplog: pytest.LogCaptureFixture) -> None:
    """Test reading a file text in the event loop logs."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        Path("/config/data_not_exist").read_text(encoding="utf8"),  # noqa: ASYNC230
    ):
        pass

    assert "Detected blocking call to read_text with args" in caplog.text


async def test_protect_path_write_bytes(caplog: pytest.LogCaptureFixture) -> None:
    """Test writing file bytes in the event loop logs."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        Path("/config/data/not/exist").write_bytes(b"xxx"),  # noqa: ASYNC230
    ):
        pass

    assert "Detected blocking call to write_bytes with args" in caplog.text


async def test_protect_path_write_text(caplog: pytest.LogCaptureFixture) -> None:
    """Test writing file text in the event loop logs."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        Path("/config/data/not/exist").write_text("xxx", encoding="utf8"),  # noqa: ASYNC230
    ):
        pass

    assert "Detected blocking call to write_text with args" in caplog.text


async def test_enable_multiple_times(caplog: pytest.LogCaptureFixture) -> None:
    """Test trying to enable multiple times."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()

    with pytest.raises(
        RuntimeError, match="Blocking call detection is already enabled"
    ):
        block_async_io.enable()


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
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with contextlib.suppress(FileNotFoundError), open(path, encoding="utf8"):  # noqa: ASYNC230
        pass

    assert "Detected blocking call to open with args" in caplog.text


async def test_protect_loop_glob(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test glob calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    glob.glob("/dev/null")
    assert "Detected blocking call to glob with args" in caplog.text
    caplog.clear()
    await hass.async_add_executor_job(glob.glob, "/dev/null")
    assert "Detected blocking call to glob with args" not in caplog.text


async def test_protect_loop_iglob(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test iglob calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    glob.iglob("/dev/null")
    assert "Detected blocking call to iglob with args" in caplog.text
    caplog.clear()
    await hass.async_add_executor_job(glob.iglob, "/dev/null")
    assert "Detected blocking call to iglob with args" not in caplog.text


async def test_protect_loop_scandir(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test glob calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with contextlib.suppress(FileNotFoundError):
        os.scandir("/path/that/does/not/exists")
    assert "Detected blocking call to scandir with args" in caplog.text
    caplog.clear()
    with contextlib.suppress(FileNotFoundError):
        await hass.async_add_executor_job(os.scandir, "/path/that/does/not/exists")
    assert "Detected blocking call to scandir with args" not in caplog.text


async def test_protect_loop_listdir(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test listdir calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with contextlib.suppress(FileNotFoundError):
        os.listdir("/path/that/does/not/exists")
    assert "Detected blocking call to listdir with args" in caplog.text
    caplog.clear()
    with contextlib.suppress(FileNotFoundError):
        await hass.async_add_executor_job(os.listdir, "/path/that/does/not/exists")
    assert "Detected blocking call to listdir with args" not in caplog.text


async def test_protect_loop_walk(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test os.walk calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    with contextlib.suppress(FileNotFoundError):
        os.walk("/path/that/does/not/exists")
    assert "Detected blocking call to walk with args" in caplog.text
    caplog.clear()
    with contextlib.suppress(FileNotFoundError):
        await hass.async_add_executor_job(os.walk, "/path/that/does/not/exists")
    assert "Detected blocking call to walk with args" not in caplog.text


async def test_protect_loop_load_default_certs(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test SSLContext.load_default_certs calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    context = ssl.create_default_context()
    assert "Detected blocking call to load_default_certs" in caplog.text
    assert context


async def test_protect_loop_load_verify_locations(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test SSLContext.load_verify_locations calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    context = ssl.create_default_context()
    with pytest.raises(OSError):
        context.load_verify_locations("/dev/null")
    assert "Detected blocking call to load_verify_locations" in caplog.text

    # ignore with only cadata
    caplog.clear()
    with pytest.raises(ssl.SSLError):
        context.load_verify_locations(cadata="xxx")
    assert "Detected blocking call to load_verify_locations" not in caplog.text


async def test_protect_loop_load_cert_chain(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test SSLContext.load_cert_chain calls in the loop are logged."""
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()
    context = ssl.create_default_context()
    with pytest.raises(OSError):
        context.load_cert_chain("/dev/null")
    assert "Detected blocking call to load_cert_chain" in caplog.text


async def test_open_calls_ignored_in_tests(caplog: pytest.LogCaptureFixture) -> None:
    """Test opening a file in tests is ignored."""
    assert block_async_io._IN_TESTS
    block_async_io.enable()
    with (
        contextlib.suppress(FileNotFoundError),
        open("/config/data_not_exist", encoding="utf8"),  # noqa: ASYNC230
    ):
        pass

    assert "Detected blocking call to open with args" not in caplog.text
