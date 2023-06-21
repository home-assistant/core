"""Test the sma sensor platform."""
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower
from homeassistant.core import HomeAssistant


async def test_sensors(hass: HomeAssistant, init_integration) -> None:
    """Test states of the sensors."""
    state = hass.states.get("sensor.sma_device_grid_power")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
