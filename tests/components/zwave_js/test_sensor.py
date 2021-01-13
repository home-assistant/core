"""Test the Z-Wave JS sensor platform."""
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
)

from .common import AIR_TEMPERATURE_SENSOR, ENERGY_SENSOR, POWER_SENSOR


async def test_numeric_sensor(hass, multisensor_6, integration):
    """Test the numeric sensor."""
    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state == "9.0"
    assert state.attributes["unit_of_measurement"] == TEMP_CELSIUS
    assert state.attributes["device_class"] == DEVICE_CLASS_TEMPERATURE


async def test_energy_sensors(hass, hank_binary_switch, integration):
    """Test power and energy sensors."""
    state = hass.states.get(POWER_SENSOR)

    assert state
    assert state.state == "0.0"
    assert state.attributes["unit_of_measurement"] == POWER_WATT
    assert state.attributes["device_class"] == DEVICE_CLASS_POWER

    state = hass.states.get(ENERGY_SENSOR)

    assert state
    assert state.state == "0.16"
    assert state.attributes["unit_of_measurement"] == ENERGY_KILO_WATT_HOUR
    assert state.attributes["device_class"] == DEVICE_CLASS_ENERGY
