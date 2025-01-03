"""The sensor tests for the tado platform."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_air_con_create_sensors(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test creation of aircon sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.air_conditioning_tado_mode")
    assert state.state == "HOME"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.air_conditioning_temperature")
    assert state.state == "24.76"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.air_conditioning_ac")
    assert state.state == "ON"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.air_conditioning_humidity")
    assert state.state == "60.9"
    assert state.attributes == snapshot


async def test_home_create_sensors(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test creation of home sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.home_name_outdoor_temperature")
    assert state.state == "7.46"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.home_name_solar_percentage")
    assert state.state == "2.1"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.home_name_weather_condition")
    assert state.state == "fog"
    assert state.attributes == snapshot


async def test_heater_create_sensors(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test creation of heater sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.baseboard_heater_tado_mode")
    assert state.state == "HOME"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.baseboard_heater_temperature")
    assert state.state == "20.65"
    assert state.attributes == snapshot

    state = hass.states.get("sensor.baseboard_heater_humidity")
    assert state.state == "45.2"
    assert state.attributes == snapshot


async def test_water_heater_create_sensors(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test creation of water heater sensors."""

    await async_init_integration(hass)

    state = hass.states.get("sensor.water_heater_tado_mode")
    assert state.state == "HOME"
    assert state.attributes == snapshot
