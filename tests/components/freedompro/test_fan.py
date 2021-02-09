"""Tests for the Freedompro fan."""
from homeassistant.components.fan import DOMAIN as LIGHT_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON

from tests.components.freedompro import init_integration


async def test_fan_get_state(hass):
    """Test states of the fan."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    entity_id = "fan.bedroom_fan"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "Bedroom fan"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS"
    )


async def test_fan_set_on(hass):
    """Test set on of the fan."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    entity_id = "fan.bedroom_fan"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "Bedroom fan"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS"
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
