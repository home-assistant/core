"""Test the sma sensor platform."""
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, POWER_WATT


async def test_sensors(hass, init_integration):
    """Test states of the sensors."""
    state = hass.states.get("sensor.sma_device_grid_power")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
