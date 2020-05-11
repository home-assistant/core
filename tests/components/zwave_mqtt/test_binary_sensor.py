"""Test Z-Wave Sensors."""
from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION
from homeassistant.const import ATTR_DEVICE_CLASS

from .common import setup_zwave


async def test_binary_sensor(hass, generic_data):
    """Test setting up config entry."""
    await setup_zwave(hass, fixture=generic_data)

    # Test Legacy sensor (disabled by default)
    registry = await hass.helpers.entity_registry.async_get_registry()
    entity_id = "binary_sensor.trisensor_sensor"
    state = hass.states.get(entity_id)
    assert state is None
    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"

    # Test sensor for Notification CC
    state = hass.states.get("binary_sensor.trisensor_home_security_motion_detected")
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MOTION
