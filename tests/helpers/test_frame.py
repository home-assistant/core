"""Test the frame helper."""

from unittest.mock import ANY, Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

from tests.common import extract_stack_to_frame


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


async def test_get_integration_logger(
    caplog: pytest.LogCaptureFixture, mock_integration_frame: Mock
) -> None:
    """Test extracting the current frame to get the logger."""
    logger = frame.get_integration_logger(__name__)
    assert logger.name == "homeassistant.components.hue"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_extract_frame_resolve_module(hass: HomeAssistant) -> None:
    """Test extracting the current frame from integration context."""
    # pylint: disable-next=import-outside-toplevel
    from custom_components.test_integration_frame import call_get_integration_frame

    integration_frame = call_get_integration_frame()

    assert integration_frame == frame.IntegrationFrame(
        custom_integration=True,
        frame=ANY,
        integration="test_integration_frame",
        module="custom_components.test_integration_frame",
        relative_filename="custom_components/test_integration_frame/__init__.py",
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_get_integration_logger_resolve_module(hass: HomeAssistant) -> None:
    """Test getting the logger from integration context."""
    # pylint: disable-next=import-outside-toplevel
    from custom_components.test_integration_frame import call_get_integration_logger

    logger = call_get_integration_logger(__name__)

    assert logger.name == "custom_components.test_integration_frame"


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
        "homeassistant.helpers.frame.get_current_frame",
        return_value=extract_stack_to_frame(
            [
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
            ]
        ),
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
    with (
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
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
                ]
            ),
        ),
        pytest.raises(frame.MissingIntegrationFrame),
    ):
        frame.get_integration_frame()


async def test_get_integration_logger_no_integration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting fallback logger without integration context."""
    with patch(
        "homeassistant.helpers.frame.get_current_frame",
        return_value=extract_stack_to_frame(
            [
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
            ]
        ),
    ):
        logger = frame.get_integration_logger(__name__)

    assert logger.name == __name__


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

        caplog.clear()

        frame.report(what, error_if_core=False, log_custom_component_only=True)
        assert caplog.text == ""


@pytest.mark.parametrize("run_count", [1, 2])
# Run this twice to make sure the flood check does not
# kick in when error_if_integration=True
async def test_report_error_if_integration(
    caplog: pytest.LogCaptureFixture, run_count: int
) -> None:
    """Test RuntimeError is raised if error_if_integration is set."""
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
            "homeassistant.helpers.frame.get_current_frame",
            return_value=frames,
        ),
        pytest.raises(
            RuntimeError,
            match=(
                "Detected that integration 'hue' did a bad"
                " thing at homeassistant/components/hue/light.py"
            ),
        ),
    ):
        frame.report("did a bad thing", error_if_integration=True)
