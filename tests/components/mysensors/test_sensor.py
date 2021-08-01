"""Provide tests for mysensors sensor platform."""


from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_POWER,
    POWER_WATT,
)


async def test_gps_sensor(hass, gps_sensor, integration):
    """Test a gps sensor."""
    entity_id = "sensor.gps_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state.state == "40.741894,-73.989311,12"


async def test_power_sensor(hass, power_sensor, integration):
    """Test a power sensor."""
    entity_id = "sensor.power_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state.state == "1200"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_POWER
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == POWER_WATT
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
