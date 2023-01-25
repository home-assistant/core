"""The sensor tests for the Airzone platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_sensors(
    hass: HomeAssistant, entity_registry_enabled_by_default: AsyncMock
) -> None:
    """Test creation of sensors."""

    await async_init_integration(hass)

    # WebServer
    state = hass.states.get("sensor.webserver_rssi")
    assert state.state == "-42"

    # Zones
    state = hass.states.get("sensor.despacho_temperature")
    assert state.state == "21.20"

    state = hass.states.get("sensor.despacho_humidity")
    assert state.state == "36"

    state = hass.states.get("sensor.dorm_1_temperature")
    assert state.state == "20.8"

    state = hass.states.get("sensor.dorm_1_humidity")
    assert state.state == "35"

    state = hass.states.get("sensor.dorm_2_temperature")
    assert state.state == "20.5"

    state = hass.states.get("sensor.dorm_2_humidity")
    assert state.state == "40"

    state = hass.states.get("sensor.dorm_ppal_temperature")
    assert state.state == "21.1"

    state = hass.states.get("sensor.dorm_ppal_humidity")
    assert state.state == "39"

    state = hass.states.get("sensor.salon_temperature")
    assert state.state == "19.6"

    state = hass.states.get("sensor.salon_humidity")
    assert state.state == "34"

    state = hass.states.get("sensor.airzone_2_1_temperature")
    assert state.state == "22.3"

    state = hass.states.get("sensor.airzone_2_1_humidity")
    assert state.state == "62"
