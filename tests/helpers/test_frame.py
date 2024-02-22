"""Test the frame helper."""

from collections.abc import Generator
from unittest.mock import ANY, Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame


@pytest.fixture
def mock_integration_frame() -> Generator[Mock, None, None]:
    """Mock as if we're calling code from inside an integration."""
    correct_frame = Mock(
        filename="/home/paulus/homeassistant/components/hue/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            correct_frame,
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        yield correct_frame


async def test_extract_frame_integration(
    caplog: pytest.LogCaptureFixture, mock_integration_frame: Mock
) -> None:
    """Test extracting the current frame from integration context."""
    integration_frame = frame.get_integration_frame()
    assert integration_frame == frame.IntegrationFrame(
        custom_integration=False,
        frame=mock_integration_frame,
        integration="hue",
        module=None,
        relative_filename="homeassistant/components/hue/light.py",
    )


async def test_extract_frame_resolve_module(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """Test extracting the current frame from integration context."""
    from custom_components.test_integration_frame import call_get_integration_frame

    integration_frame = call_get_integration_frame()

    assert integration_frame == frame.IntegrationFrame(
        custom_integration=True,
        frame=ANY,
        integration="test_integration_frame",
        module="custom_components.test_integration_frame",
        relative_filename="custom_components/test_integration_frame/__init__.py",
    )


async def test_extract_frame_integration_with_excluded_integration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test extracting the current frame from integration context."""
    correct_frame = Mock(
        filename="/home/dev/homeassistant/components/mdns/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/home/dev/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            correct_frame,
            Mock(
                filename="/home/dev/homeassistant/components/zeroconf/usage.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/home/dev/mdns/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        integration_frame = frame.get_integration_frame(
            exclude_integrations={"zeroconf"}
        )

    assert integration_frame == frame.IntegrationFrame(
        custom_integration=False,
        frame=correct_frame,
        integration="mdns",
        module=None,
        relative_filename="homeassistant/components/mdns/light.py",
    )


async def test_extract_frame_no_integration(caplog: pytest.LogCaptureFixture) -> None:
    """Test extracting the current frame without integration context."""
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ), pytest.raises(frame.MissingIntegrationFrame):
        frame.get_integration_frame()


@patch.object(frame, "_REPORTED_INTEGRATIONS", set())
async def test_prevent_flooding(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_integration_frame: Mock
) -> None:
    """Test to ensure a report is only written once to the log."""

    what = "accessed hi instead of hello"
    key = "/home/paulus/homeassistant/components/hue/light.py:23"
    integration = "hue"
    filename = "homeassistant/components/hue/light.py"

    expected_message = (
        f"Detected that integration '{integration}' {what} at {filename}, line "
        f"{mock_integration_frame.lineno}: {mock_integration_frame.line}, "
        f"please create a bug report at https://github.com/home-assistant/core/issues?"
        f"q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+{integration}%22"
    )

    frame.report(what, error_if_core=False)
    assert expected_message in caplog.text
    assert key in frame._REPORTED_INTEGRATIONS
    assert len(frame._REPORTED_INTEGRATIONS) == 1

    caplog.clear()

    frame.report(what, error_if_core=False)
    assert expected_message not in caplog.text
    assert key in frame._REPORTED_INTEGRATIONS
    assert len(frame._REPORTED_INTEGRATIONS) == 1


async def test_report_missing_integration_frame(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reporting when no integration is detected."""

    what = "teststring"
    with patch(
        "homeassistant.helpers.frame.get_integration_frame",
        side_effect=frame.MissingIntegrationFrame,
    ):
        frame.report(what, error_if_core=False)
        assert what in caplog.text
        assert caplog.text.count(what) == 1
