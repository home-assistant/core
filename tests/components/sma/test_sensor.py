"""Test the sma sensor platform."""
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)

from . import MOCK_CUSTOM_SENSOR


async def test_sensors(hass, init_integration):
    """Test states of the sensors."""
    state = hass.states.get("sensor.current_consumption")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT

    state = hass.states.get(f"sensor.{MOCK_CUSTOM_SENSOR['name']}")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
