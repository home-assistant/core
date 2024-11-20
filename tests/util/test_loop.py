"""Tests for async util methods from Python source."""

from collections.abc import Generator
import contextlib
import threading
from unittest.mock import Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util import loop as haloop

from tests.common import extract_stack_to_frame


def banned_function():
    """Mock banned function."""


@contextlib.contextmanager
def patch_get_current_frame(stack: list[Mock]) -> Generator[None]:
    """Patch get_current_frame."""
    frames = extract_stack_to_frame(stack)
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value=stack[1].line,
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
        yield


async def test_raise_for_blocking_call_async() -> None:
    """Test raise_for_blocking_call detects when called from event loop without integration context."""
    with pytest.raises(RuntimeError):
        haloop.raise_for_blocking_call(banned_function)


async def test_raise_for_blocking_call_async_non_strict_core(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test non_strict_core raise_for_blocking_call detects from event loop without integration context."""
    stack = [
        Mock(
            filename="/home/paulus/homeassistant/core.py",
            lineno="12",
            line="do_something()",
        ),
        Mock(
            filename="/home/paulus/homeassistant/core.py",
            lineno="12",
            line="self.light.is_on",
        ),
        Mock(
            filename="/home/paulus/aiohue/lights.py",
            lineno="2",
            line="something()",
        ),
    ]
    with patch_get_current_frame(stack):
        haloop.raise_for_blocking_call(banned_function, strict_core=False)
    assert "Detected blocking call to banned_function" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert (
        "Please create a bug report at https://github.com/home-assistant/core/issues"
        in caplog.text
    )
    assert (
        "For developers, please see "
        "https://developers.home-assistant.io/docs/asyncio_blocking_operations/#banned_function"
    ) in caplog.text

    warnings = [
        record for record in caplog.get_records("call") if record.levelname == "WARNING"
    ]
    assert len(warnings) == 1
    caplog.clear()

    # Second call should log at debug
    with patch_get_current_frame(stack):
        haloop.raise_for_blocking_call(banned_function, strict_core=False)

    warnings = [
        record for record in caplog.get_records("call") if record.levelname == "WARNING"
    ]
    assert len(warnings) == 0
    assert (
        "For developers, please see "
        "https://developers.home-assistant.io/docs/asyncio_blocking_operations/#banned_function"
    ) in caplog.text

    # no expensive traceback on debug
    assert "Traceback (most recent call last)" not in caplog.text


async def test_raise_for_blocking_call_async_integration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test raise_for_blocking_call detects and raises when called from event loop from integration context."""
    stack = [
        Mock(
            filename="/home/paulus/homeassistant/core.py",
            lineno="18",
            line="do_something()",
        ),
        Mock(
            filename="/home/paulus/homeassistant/components/hue/light.py",
            lineno="18",
            line="self.light.is_on",
        ),
        Mock(
            filename="/home/paulus/aiohue/lights.py",
            lineno="8",
            line="something()",
        ),
    ]
    with (
        pytest.raises(RuntimeError),
        patch_get_current_frame(stack),
    ):
        haloop.raise_for_blocking_call(banned_function)
    assert (
        "Detected blocking call to banned_function with args None"
        " inside the event loop by integration"
        " 'hue' at homeassistant/components/hue/light.py, line 18: self.light.is_on "
        "(offender: /home/paulus/aiohue/lights.py, line 8: mock_line), please create "
        "a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22" in caplog.text
    )
    assert (
        "For developers, please see "
        "https://developers.home-assistant.io/docs/asyncio_blocking_operations/#banned_function"
    ) in caplog.text


async def test_raise_for_blocking_call_async_integration_non_strict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test raise_for_blocking_call detects when called from event loop from integration context."""
    stack = [
        Mock(
            filename="/home/paulus/homeassistant/core.py",
            lineno="15",
            line="do_something()",
        ),
        Mock(
            filename="/home/paulus/homeassistant/components/hue/light.py",
            lineno="15",
            line="self.light.is_on",
        ),
        Mock(
            filename="/home/paulus/aiohue/lights.py",
            lineno="1",
            line="something()",
        ),
    ]
    with patch_get_current_frame(stack):
        haloop.raise_for_blocking_call(banned_function, strict=False)

    assert (
        "Detected blocking call to banned_function with args None"
        " inside the event loop by integration"
        " 'hue' at homeassistant/components/hue/light.py, line 15: self.light.is_on "
        "(offender: /home/paulus/aiohue/lights.py, line 1: mock_line), "
        "please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22" in caplog.text
    )
    assert "Traceback (most recent call last)" in caplog.text
    assert (
        'File "/home/paulus/homeassistant/components/hue/light.py", line 15'
        in caplog.text
    )
    assert (
        "please create a bug report at https://github.com/home-assistant/core/issues"
        in caplog.text
    )
    assert (
        "For developers, please see "
        "https://developers.home-assistant.io/docs/asyncio_blocking_operations/#banned_function"
    ) in caplog.text
    warnings = [
        record for record in caplog.get_records("call") if record.levelname == "WARNING"
    ]
    assert len(warnings) == 1
    caplog.clear()

    # Second call should log at debug
    with patch_get_current_frame(stack):
        haloop.raise_for_blocking_call(banned_function, strict=False)

    warnings = [
        record for record in caplog.get_records("call") if record.levelname == "WARNING"
    ]
    assert len(warnings) == 0
    assert (
        "For developers, please see "
        "https://developers.home-assistant.io/docs/asyncio_blocking_operations/#banned_function"
    ) in caplog.text
    # no expensive traceback on debug
    assert "Traceback (most recent call last)" not in caplog.text


async def test_raise_for_blocking_call_async_custom(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test raise_for_blocking_call detects when called from event loop with custom component context."""
    stack = [
        Mock(
            filename="/home/paulus/homeassistant/core.py",
            lineno="12",
            line="do_something()",
        ),
        Mock(
            filename="/home/paulus/config/custom_components/hue/light.py",
            lineno="12",
            line="self.light.is_on",
        ),
        Mock(
            filename="/home/paulus/aiohue/lights.py",
            lineno="3",
            line="something()",
        ),
    ]
    with pytest.raises(RuntimeError), patch_get_current_frame(stack):
        haloop.raise_for_blocking_call(banned_function)
    assert (
        "Detected blocking call to banned_function with args None"
        " inside the event loop by custom "
        "integration 'hue' at custom_components/hue/light.py, line 12: self.light.is_on"
        " (offender: /home/paulus/aiohue/lights.py, line 3: mock_line), "
        "please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert (
        'File "/home/paulus/config/custom_components/hue/light.py", line 12'
        in caplog.text
    )
    assert (
        "For developers, please see "
        "https://developers.home-assistant.io/docs/asyncio_blocking_operations/#banned_function"
    ) in caplog.text


async def test_raise_for_blocking_call_sync(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test raise_for_blocking_call does nothing when called from thread."""
    func = haloop.protect_loop(banned_function, threading.get_ident())
    await hass.async_add_executor_job(func)
    assert "Detected blocking call inside the event loop" not in caplog.text


async def test_protect_loop_async() -> None:
    """Test protect_loop calls raise_for_blocking_call."""
    func = Mock()
    with patch(
        "homeassistant.util.loop.raise_for_blocking_call"
    ) as mock_raise_for_blocking_call:
        haloop.protect_loop(func, threading.get_ident())(1, test=2)
    mock_raise_for_blocking_call.assert_called_once_with(
        func,
        strict=True,
        args=(1,),
        check_allowed=None,
        kwargs={"test": 2},
        strict_core=True,
    )
    func.assert_called_once_with(1, test=2)
