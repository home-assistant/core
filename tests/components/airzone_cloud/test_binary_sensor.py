"""The binary sensor tests for the Airzone Cloud platform."""

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_binary_sensors(hass: HomeAssistant) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    # Zones
    state = hass.states.get("binary_sensor.dormitorio_problem")
    assert state.state == STATE_OFF
    assert state.attributes.get("warnings") is None

    state = hass.states.get("binary_sensor.salon_problem")
    assert state.state == STATE_OFF
    assert state.attributes.get("warnings") is None
