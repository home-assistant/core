"""Test Z-Wave Sensors."""
from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.components.zwave_mqtt.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS

from .common import setup_zwave


async def test_sensor(hass, generic_data):
    """Test setting up config entry."""
    await setup_zwave(hass, fixture=generic_data)

    # Test standard sensor
    state = hass.states.get("sensor.smart_plug_electric_v")
    assert state is not None
    assert state.state == "123.9"
    assert state.attributes["unit_of_measurement"] == "V"

    # Test device classes
    state = hass.states.get("sensor.trisensor_relative_humidity")
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_HUMIDITY
    state = hass.states.get("sensor.trisensor_pressure")
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_PRESSURE
    state = hass.states.get("sensor.trisensor_fake_power")
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_POWER
    state = hass.states.get("sensor.trisensor_fake_energy")
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_POWER
    state = hass.states.get("sensor.trisensor_fake_electric")
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_POWER

    # Test ZWaveListSensor disabled by default
    registry = await hass.helpers.entity_registry.async_get_registry()
    entity_id = "sensor.water_sensor_6_instance_1_water"
    state = hass.states.get(entity_id)
    assert state is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"

    # Test enabling entity
    updated_entry = registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_sensor_enabled(hass, generic_data, sensor_msg):
    """Test enabling an advanced sensor."""

    registry = await hass.helpers.entity_registry.async_get_registry()

    entry = registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "1-36-1407375493578772",
        suggested_object_id="water_sensor_6_instance_1_water",
        disabled_by=None,
    )
    assert entry.disabled is False

    receive_msg = await setup_zwave(hass, fixture=generic_data)
    receive_msg(sensor_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entry.entity_id)
    assert state is not None
    assert state.state == "0"
    assert state.attributes["label"] == "Clear"
