"""Test the frame helper."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.helpers import frame


async def test_extract_frame_integration(
    caplog: pytest.LogCaptureFixture, mock_integration_frame: Mock
) -> None:
    """Test extracting the current frame from integration context."""
    found_frame, integration, path = frame.get_integration_frame()

    assert integration == "hue"
    assert path == "homeassistant/components/"
    assert found_frame == mock_integration_frame


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
        found_frame, integration, path = frame.get_integration_frame(
            exclude_integrations={"zeroconf"}
        )

    assert integration == "mdns"
    assert path == "homeassistant/components/"
    assert found_frame == correct_frame


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


@pytest.mark.usefixtures("mock_integration_frame")
@patch.object(frame, "_REPORTED_INTEGRATIONS", set())
async def test_prevent_flooding(caplog: pytest.LogCaptureFixture) -> None:
    """Test to ensure a report is only written once to the log."""

    what = "accessed hi instead of hello"
    key = "/home/paulus/homeassistant/components/hue/light.py:23"

    frame.report(what, error_if_core=False)
    assert what in caplog.text
    assert key in frame._REPORTED_INTEGRATIONS
    assert len(frame._REPORTED_INTEGRATIONS) == 1

    caplog.clear()

    frame.report(what, error_if_core=False)
    assert what not in caplog.text
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
