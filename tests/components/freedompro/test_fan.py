"""Tests for the Freedompro fan."""
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, STATE_OFF
from homeassistant.helpers import entity_registry as er


async def test_fan_get_state(hass, init_integration):
    """Test states of the fan."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "fan.bedroom"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "bedroom"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS"
    )


async def test_fan_set_on(hass, init_integration):
    """Test set on of the fan."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "fan.bedroom"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "bedroom"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS"
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_fan_set_off(hass, init_integration):
    """Test set off of the fan."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "fan.bedroom"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "bedroom"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS"
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
