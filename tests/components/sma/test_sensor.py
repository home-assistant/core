"""Test the sma sensor platform."""
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)

from . import MOCK_CUSTOM_SENSOR, init_integration


async def test_sensors(hass):
    """Test states of the sensors."""
    await init_integration(hass)

    state = hass.states.get("sensor.current_consumption")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT

    state = hass.states.get(f"sensor.{MOCK_CUSTOM_SENSOR['name']}")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
