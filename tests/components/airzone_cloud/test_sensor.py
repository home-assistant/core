"""The sensor tests for the Airzone Cloud platform."""

from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_sensors(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test creation of sensors."""

    await async_init_integration(hass)

    # Aidoos
    state = hass.states.get("sensor.bron_temperature")
    assert state.state == "21.0"

    state = hass.states.get("sensor.bron_pro_temperature")
    assert state.state == "20.0"

    # WebServers
    state = hass.states.get("sensor.webserver_11_22_33_44_55_66_signal_strength")
    assert state.state == "-56"

    state = hass.states.get("sensor.webserver_11_22_33_44_55_67_signal_strength")
    assert state.state == "-77"

    # Zones
    state = hass.states.get("sensor.dormitorio_air_quality_index")
    assert state.state == "1"

    state = hass.states.get("sensor.dormitorio_pm1")
    assert state.state == "3"

    state = hass.states.get("sensor.dormitorio_pm2_5")
    assert state.state == "4"

    state = hass.states.get("sensor.dormitorio_pm10")
    assert state.state == "3"

    state = hass.states.get("sensor.dormitorio_temperature")
    assert state.state == "25.0"

    state = hass.states.get("sensor.dormitorio_humidity")
    assert state.state == "24"

    state = hass.states.get("sensor.dormitorio_air_quality_index")
    assert state.state == "1"

    state = hass.states.get("sensor.salon_pm1")
    assert state.state == "3"

    state = hass.states.get("sensor.salon_pm2_5")
    assert state.state == "4"

    state = hass.states.get("sensor.salon_pm10")
    assert state.state == "3"

    state = hass.states.get("sensor.salon_temperature")
    assert state.state == "20.0"

    state = hass.states.get("sensor.salon_humidity")
    assert state.state == "30"
