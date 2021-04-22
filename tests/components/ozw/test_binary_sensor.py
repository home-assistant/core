"""Test Z-Wave Sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.ozw.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.helpers import entity_registry as er

from .common import setup_ozw


async def test_binary_sensor(hass, generic_data, binary_sensor_msg):
    """Test setting up config entry."""
    receive_msg = await setup_ozw(hass, fixture=generic_data)

    # Test Legacy sensor (disabled by default)
    registry = er.async_get(hass)
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


async def test_sensor_enabled(hass, generic_data, binary_sensor_alt_msg):
    """Test enabling a legacy binary_sensor."""

    registry = er.async_get(hass)

    entry = registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        "1-37-625737744",
        suggested_object_id="trisensor_sensor_instance_1_sensor",
        disabled_by=None,
    )
    assert entry.disabled is False

    receive_msg = await setup_ozw(hass, fixture=generic_data)
    receive_msg(binary_sensor_alt_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entry.entity_id)
    assert state is not None
    assert state.state == "on"
