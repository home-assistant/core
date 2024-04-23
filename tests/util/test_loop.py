"""Tests for async util methods from Python source."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.util import loop as haloop

from tests.common import extract_stack_to_frame


def banned_function():
    """Mock banned function."""


async def test_check_loop_async() -> None:
    """Test check_loop detects when called from event loop without integration context."""
    with pytest.raises(RuntimeError):
        haloop.check_loop(banned_function)


async def test_check_loop_async_non_strict_core(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test non_strict_core check_loop detects from event loop without integration context."""
    haloop.check_loop(banned_function, strict_core=False)
    assert "Detected blocking call to banned_function" in caplog.text


async def test_check_loop_async_integration(caplog: pytest.LogCaptureFixture) -> None:
    """Test check_loop detects and raises when called from event loop from integration context."""
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
        pytest.raises(RuntimeError),
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
        haloop.check_loop(banned_function)
    assert (
        "Detected blocking call to banned_function inside the event loop by integration"
        " 'hue' at homeassistant/components/hue/light.py, line 23: self.light.is_on "
        "(offender: /home/paulus/aiohue/lights.py, line 2: mock_line), please create "
        "a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22" in caplog.text
    )


async def test_check_loop_async_integration_non_strict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test check_loop detects when called from event loop from integration context."""
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
        haloop.check_loop(banned_function, strict=False)
    assert (
        "Detected blocking call to banned_function inside the event loop by integration"
        " 'hue' at homeassistant/components/hue/light.py, line 23: self.light.is_on "
        "(offender: /home/paulus/aiohue/lights.py, line 2: mock_line), "
        "please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22" in caplog.text
    )


async def test_check_loop_async_custom(caplog: pytest.LogCaptureFixture) -> None:
    """Test check_loop detects when called from event loop with custom component context."""
    frames = extract_stack_to_frame(
        [
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
        ]
    )
    with (
        pytest.raises(RuntimeError),
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
        haloop.check_loop(banned_function)
    assert (
        "Detected blocking call to banned_function inside the event loop by custom "
        "integration 'hue' at custom_components/hue/light.py, line 23: self.light.is_on"
        " (offender: /home/paulus/aiohue/lights.py, line 2: mock_line), "
        "please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text


def test_check_loop_sync(caplog: pytest.LogCaptureFixture) -> None:
    """Test check_loop does nothing when called from thread."""
    haloop.check_loop(banned_function)
    assert "Detected blocking call inside the event loop" not in caplog.text


def test_protect_loop_sync() -> None:
    """Test protect_loop calls check_loop."""
    func = Mock()
    with patch("homeassistant.util.loop.check_loop") as mock_check_loop:
        haloop.protect_loop(func)(1, test=2)
    mock_check_loop.assert_called_once_with(
        func,
        strict=True,
        args=(1,),
        check_allowed=None,
        kwargs={"test": 2},
        strict_core=True,
    )
    func.assert_called_once_with(1, test=2)
