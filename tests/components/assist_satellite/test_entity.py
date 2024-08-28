"""Test the Assist Satellite entity."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

ENTITY_ID = "assist_satellite.test_entity"


async def test_entity_state(hass: HomeAssistant, init_components: ConfigEntry) -> None:
    """Test entity state represent events."""

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
