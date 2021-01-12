"""Test the Z-Wave JS sensor platform."""
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS

from .common import AIR_TEMPERATURE_SENSOR


async def test_numeric_sensor(hass, multisensor_6, integration):
    """Test the numeric sensor."""
    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state == "9.0"
    assert state.attributes["unit_of_measurement"] == TEMP_CELSIUS
    assert state.attributes["device_class"] == DEVICE_CLASS_TEMPERATURE
