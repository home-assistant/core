"""Tests for the Lyngdorf sensor platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensor_entities_created(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test that sensor entities are created."""
    assert init_integration.state.value == "loaded"

    sensor_keys = [
        "audio_information",
        "video_information",
        "audio_input",
        "video_input",
        "streaming_source",
        "zone_b_audio_input",
        "zone_b_streaming_source",
    ]
    for key in sensor_keys:
        state = hass.states.get(f"sensor.mock_lyngdorf_{key}")
        assert state is not None, f"sensor.mock_lyngdorf_{key} not found"


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

    # Trigger callback to update states
    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
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

    # Trigger callback to update states
    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
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
    assert state.state == "unknown"
