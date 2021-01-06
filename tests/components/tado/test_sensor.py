"""The sensor tests for the tado platform."""

from .util import async_init_integration


async def test_air_con_create_sensors(hass):
    """Test creation of aircon sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.air_conditioning_power")
    assert state.state == "ON"

    state = hass.states.get("sensor.air_conditioning_link")
    assert state.state == "ONLINE"

    state = hass.states.get("sensor.air_conditioning_link")
    assert state.state == "ONLINE"

    state = hass.states.get("sensor.air_conditioning_tado_mode")
    assert state.state == "HOME"

    state = hass.states.get("sensor.air_conditioning_temperature")
    assert state.state == "24.76"

    state = hass.states.get("sensor.air_conditioning_ac")
    assert state.state == "ON"

    state = hass.states.get("sensor.air_conditioning_overlay")
    assert state.state == "True"

    state = hass.states.get("sensor.air_conditioning_humidity")
    assert state.state == "60.9"

    state = hass.states.get("sensor.air_conditioning_open_window")
    assert state.state == "False"


async def test_heater_create_sensors(hass):
    """Test creation of heater sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.baseboard_heater_power")
    assert state.state == "ON"

    state = hass.states.get("sensor.baseboard_heater_link")
    assert state.state == "ONLINE"

    state = hass.states.get("sensor.baseboard_heater_link")
    assert state.state == "ONLINE"

    state = hass.states.get("sensor.baseboard_heater_tado_mode")
    assert state.state == "HOME"

    state = hass.states.get("sensor.baseboard_heater_temperature")
    assert state.state == "20.65"

    state = hass.states.get("sensor.baseboard_heater_early_start")
    assert state.state == "False"

    state = hass.states.get("sensor.baseboard_heater_overlay")
    assert state.state == "True"

    state = hass.states.get("sensor.baseboard_heater_humidity")
    assert state.state == "45.2"

    state = hass.states.get("sensor.baseboard_heater_open_window")
    assert state.state == "False"


async def test_water_heater_create_sensors(hass):
    """Test creation of water heater sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.water_heater_tado_mode")
    assert state.state == "HOME"

    state = hass.states.get("sensor.water_heater_link")
    assert state.state == "ONLINE"

    state = hass.states.get("sensor.water_heater_overlay")
    assert state.state == "False"

    state = hass.states.get("sensor.water_heater_power")
    assert state.state == "ON"
