"""Test the frame helper."""
import pytest

from homeassistant.helpers import frame

from tests.async_mock import Mock, patch


async def test_extract_frame_integration(caplog):
    """Test extracting the current frame from integration context."""
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
        found_frame, integration, path = frame.get_integration_frame()

    assert integration == "hue"
    assert path == "homeassistant/components/"
    assert found_frame == correct_frame


async def test_extract_frame_integration_with_excluded_intergration(caplog):
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
            Mock(filename="/home/dev/mdns/lights.py", lineno="2", line="something()",),
        ],
    ):
        found_frame, integration, path = frame.get_integration_frame(
            exclude_integrations={"zeroconf"}
        )

    assert integration == "mdns"
    assert path == "homeassistant/components/"
    assert found_frame == correct_frame


async def test_extract_frame_no_integration(caplog):
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
