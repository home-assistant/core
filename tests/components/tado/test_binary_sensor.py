"""The sensor tests for the tado platform."""

from homeassistant.const import STATE_OFF, STATE_ON

from .util import async_init_integration


async def test_air_con_create_binary_sensors(hass):
    """Test creation of aircon sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.air_conditioning_power")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.air_conditioning_link")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.air_conditioning_overlay")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.air_conditioning_open_window")
    assert state.state == STATE_OFF


async def test_heater_create_binary_sensors(hass):
    """Test creation of heater sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.baseboard_heater_power")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.baseboard_heater_link")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.baseboard_heater_early_start")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.baseboard_heater_overlay")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.baseboard_heater_open_window")
    assert state.state == STATE_OFF


async def test_water_heater_create_binary_sensors(hass):
    """Test creation of water heater sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.water_heater_link")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.water_heater_overlay")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.water_heater_power")
    assert state.state == STATE_ON


async def test_home_create_binary_sensors(hass):
    """Test creation of home binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.wr1_connection_state")
    assert state.state == STATE_ON
