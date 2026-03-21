"""Tests for HomematicIP Cloud siren."""

from homeassistant.components.siren import (
    ATTR_AVAILABLE_TONES,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    SirenEntityFeature,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_OFF
from homeassistant.core import HomeAssistant

from .helper import HomeFactory, async_manipulate_test_data, get_and_check_entity_basics


async def test_hmip_mp3_siren(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipMP3Siren (HmIP-MP3P)."""
    entity_id = "siren.kombisignalmelder_siren"
    entity_name = "Kombisignalmelder Siren"
    device_model = "HmIP-MP3P"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Kombisignalmelder"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    # Fixture has playingFileActive=false
    assert ha_state.state == STATE_OFF
    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.TONES
        | SirenEntityFeature.VOLUME_SET
    )
    assert len(ha_state.attributes[ATTR_AVAILABLE_TONES]) == 253

    functional_channel = hmip_device.functionalChannels[1]
    service_call_counter = len(functional_channel.mock_calls)

    # Test turn_on with tone and volume
    await hass.services.async_call(
        "siren",
        "turn_on",
        {
            "entity_id": entity_id,
            ATTR_TONE: 5,
            ATTR_VOLUME_LEVEL: 0.6,
        },
        blocking=True,
    )
    assert functional_channel.mock_calls[-1][0] == "set_sound_file_volume_level_async"
    assert functional_channel.mock_calls[-1][2] == {
        "sound_file": "SOUNDFILE_005",
        "volume_level": 0.6,
    }
    assert len(functional_channel.mock_calls) == service_call_counter + 1

    # Test turn_on with internal sound (tone=0)
    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": entity_id, ATTR_TONE: 0},
        blocking=True,
    )
    assert functional_channel.mock_calls[-1][2] == {
        "sound_file": "INTERNAL_SOUNDFILE",
        "volume_level": 1.0,
    }
    assert len(functional_channel.mock_calls) == service_call_counter + 2

    # Test turn_off
    await hass.services.async_call(
        "siren",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert functional_channel.mock_calls[-1][0] == "stop_sound_async"
    assert len(functional_channel.mock_calls) == service_call_counter + 3

    # Test state update when playing
    await async_manipulate_test_data(
        hass, hmip_device, "playingFileActive", True, channel=1
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "on"
