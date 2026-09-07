"""Tests for the Lyngdorf sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import notify_receiver_update

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the sensor platform."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("mock_receiver")
async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_none_values(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test a sensor shows unknown when the device reports nothing."""
    mock_receiver.audio_information = None
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.mock_lyngdorf_audio_information").state == STATE_UNKNOWN
    )


async def test_enum_sensor_ignores_unknown_device_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test an input the library could not name is reported as unknown."""
    mock_receiver.audio_inputs = ["optical"]
    mock_receiver.audio_input = "audio-37"

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_lyngdorf_audio_input").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("entity_id", "attribute", "value"),
    [
        pytest.param(
            "sensor.mock_lyngdorf_video_input", "video_inputs", ["DP"], id="video"
        ),
        pytest.param(
            "sensor.mock_lyngdorf_streaming_source",
            "stream_types",
            ["Spotify"],
            id="stream",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensors_read_the_current_lists_not_the_deprecated_aliases(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    entity_id: str,
    attribute: str,
    value: list[str],
) -> None:
    """Test the lists come from the 2.0 names while the aliases say otherwise."""
    setattr(mock_receiver, attribute, value)
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes["options"] == value


@pytest.mark.usefixtures("init_integration")
async def test_zone_b_sensors_read_the_zone_object(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test the Zone B sensors follow the zone, not the receiver aliases."""
    mock_receiver.zone_b.audio_input = "optical"
    mock_receiver.zone_b.streaming_source = "AirPlay"
    mock_receiver.zone_b_audio_input = "aux"
    mock_receiver.zone_b_streaming_source = "DLNA"
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_lyngdorf_zone_b_audio_input").state == "optical"
    assert (
        hass.states.get("sensor.mock_lyngdorf_zone_b_streaming_source").state
        == "AirPlay"
    )


@pytest.mark.usefixtures("init_integration")
async def test_enum_options_follow_the_device(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test enum options track the lists the device reports."""
    mock_receiver.audio_inputs = ["HDMI", "optical"]
    mock_receiver.audio_input = "HDMI"
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_lyngdorf_audio_input")
    assert state.attributes["options"] == ["HDMI", "optical"]

    mock_receiver.audio_inputs = ["HDMI", "optical", "ARC"]
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_lyngdorf_audio_input")
    assert state.attributes["options"] == ["HDMI", "optical", "ARC"]
