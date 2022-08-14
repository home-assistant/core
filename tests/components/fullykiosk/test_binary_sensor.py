"""Test the Fully Kiosk Browser binary sensors."""
from homeassistant.helpers import entity_registry as er

from tests.components.fullykiosk import init_integration


async def test_binary_sensors(hass):
    """Test standard Fully Kiosk binary sensors."""
    await init_integration(hass)
    registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.amazon_fire_plugged_in")
    assert state
    assert state.state == "on"
    entry = registry.async_get("binary_sensor.amazon_fire_plugged_in")
    assert entry
    assert entry.unique_id == "abcdef-123456-plugged"

    state = hass.states.get("binary_sensor.amazon_fire_kiosk_mode")
    assert state
    assert state.state == "on"
