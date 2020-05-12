"""Test Z-Wave Sensors."""
from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION
from homeassistant.const import ATTR_DEVICE_CLASS

from .common import setup_zwave


async def test_binary_sensor(hass, generic_data, binary_sensor_msg):
    """Test setting up config entry."""
    receive_msg = await setup_zwave(hass, fixture=generic_data)

    # Test Legacy sensor (disabled by default)
    registry = await hass.helpers.entity_registry.async_get_registry()
    entity_id = "binary_sensor.trisensor_sensor"
    state = hass.states.get(entity_id)
    assert state is None
    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"

    # Test enabling legacy entity
    updated_entry = registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False

    # Test Sensor for Notification CC
    state = hass.states.get("binary_sensor.trisensor_home_security_motion_detected")
    assert state
    assert state.state == "off"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MOTION

    # Test incoming state change
    receive_msg(binary_sensor_msg)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.trisensor_home_security_motion_detected")
    assert state.state == "on"
