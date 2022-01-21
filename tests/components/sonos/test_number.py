"""Tests for the Sonos number platform."""
from unittest.mock import patch

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import entity_registry as ent_reg


async def test_audio_input_sensor(hass, async_autosetup_sonos, soco):
    """Test audio input sensor."""
    entity_registry = ent_reg.async_get(hass)

    bass_number = entity_registry.entities["number.zone_a_bass"]
    bass_state = hass.states.get(bass_number.entity_id)
    assert bass_state.state == "1"

    treble_number = entity_registry.entities["number.zone_a_treble"]
    treble_state = hass.states.get(treble_number.entity_id)
    assert treble_state.state == "-1"

    audio_delay_number = entity_registry.entities["number.zone_a_audio_delay"]
    audio_delay_state = hass.states.get(audio_delay_number.entity_id)
    assert audio_delay_state.state == "2"

    with patch("soco.SoCo.audio_delay") as mock_audio_delay:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: audio_delay_number.entity_id, "value": 3},
            blocking=True,
        )
        assert mock_audio_delay.called_with(3)
