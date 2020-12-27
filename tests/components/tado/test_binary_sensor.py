"""The sensor tests for the tado platform."""

from homeassistant.const import STATE_ON

from .util import async_init_integration


async def test_home_create_binary_sensors(hass):
    """Test creation of home binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.wr1_connection_state")
    assert state.state == STATE_ON
