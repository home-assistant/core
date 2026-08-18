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


async def test_main_zone_sensor_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test main zone sensor values update from receiver."""
    mock_receiver.audio_information = "Stereo"
    mock_receiver.video_information = "4K HDR"
    mock_receiver.audio_input = "optical"
    mock_receiver.video_input = "hdmi"
    mock_receiver.streaming_source = "AirPlay"
    mock_receiver.available_audio_inputs = ["optical", "aux"]
    mock_receiver.available_video_inputs = ["hdmi"]
    mock_receiver.available_stream_types = ["AirPlay", "DLNA"]

    # Trigger callback to update states
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_lyngdorf_audio_information").state == "Stereo"
    assert hass.states.get("sensor.mock_lyngdorf_video_information").state == "4K HDR"
    assert hass.states.get("sensor.mock_lyngdorf_audio_input").state == "optical"
    assert hass.states.get("sensor.mock_lyngdorf_video_input").state == "hdmi"
    assert hass.states.get("sensor.mock_lyngdorf_streaming_source").state == "AirPlay"


async def test_zone_b_sensor_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test zone B sensor values update from receiver."""
    mock_receiver.zone_b_audio_input = "aux"
    mock_receiver.zone_b_streaming_source = "DLNA"
    mock_receiver.available_audio_inputs = ["optical", "aux"]
    mock_receiver.available_stream_types = ["AirPlay", "DLNA"]

    # Trigger callback to update states
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_lyngdorf_zone_b_audio_input").state == "aux"
    assert (
        hass.states.get("sensor.mock_lyngdorf_zone_b_streaming_source").state == "DLNA"
    )


async def test_sensor_none_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test sensors show unknown when receiver values are None."""
    state = hass.states.get("sensor.mock_lyngdorf_audio_information")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_enum_sensor_ignores_unknown_device_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test an input the library could not name is reported as unknown."""
    mock_receiver.available_audio_inputs = ["optical"]
    mock_receiver.audio_input = "audio-37"

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_lyngdorf_audio_input").state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_enum_options_follow_the_device(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test enum options track the lists the device reports."""
    mock_receiver.available_audio_inputs = ["HDMI", "optical"]
    mock_receiver.audio_input = "HDMI"
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_lyngdorf_audio_input")
    assert state.attributes["options"] == ["HDMI", "optical"]

    mock_receiver.available_audio_inputs = ["HDMI", "optical", "ARC"]
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_lyngdorf_audio_input")
    assert state.attributes["options"] == ["HDMI", "optical", "ARC"]
