"""The sensor tests for the Airzone Cloud platform."""

import pytest

from homeassistant.core import HomeAssistant

from .util import async_init_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_airzone_create_sensors(hass: HomeAssistant) -> None:
    """Test creation of sensors."""

    await async_init_integration(hass)

    # Aidoos
    state = hass.states.get("sensor.bron_temperature")
    assert state.state == "21.0"

    state = hass.states.get("sensor.bron_pro_temperature")
    assert state.state == "20.0"

    state = hass.states.get("sensor.bron_pro_indoor_exchanger_temperature")
    assert state.state == "26.0"

    state = hass.states.get("sensor.bron_pro_indoor_return_temperature")
    assert state.state == "26.0"

    state = hass.states.get("sensor.bron_pro_indoor_working_temperature")
    assert state.state == "25.0"

    state = hass.states.get("sensor.bron_pro_outdoor_condenser_pressure")
    assert state.state == "150.0"

    state = hass.states.get("sensor.bron_pro_outdoor_discharge_temperature")
    assert state.state == "121.0"

    state = hass.states.get("sensor.bron_pro_outdoor_electric_current")
    assert state.state == "3.0"

    state = hass.states.get("sensor.bron_pro_outdoor_evaporator_pressure")
    assert state.state == "20.0"

    state = hass.states.get("sensor.bron_pro_outdoor_exchanger_temperature")
    assert state.state == "-25.0"

    state = hass.states.get("sensor.bron_pro_outdoor_temperature")
    assert state.state == "29.0"

    # WebServers
    state = hass.states.get("sensor.webserver_11_22_33_44_55_66_cpu_usage")
    assert state.state == "32"

    state = hass.states.get("sensor.webserver_11_22_33_44_55_66_free_memory")
    assert state.state == "42616"

    state = hass.states.get("sensor.webserver_11_22_33_44_55_67_signal_strength")
    assert state.state == "-77"

    # Zones
    state = hass.states.get("sensor.dormitorio_air_quality_index")
    assert state.state == "1"

    state = hass.states.get("sensor.dormitorio_battery")
    assert state.state == "54"

    state = hass.states.get("sensor.dormitorio_pm1")
    assert state.state == "3"

    state = hass.states.get("sensor.dormitorio_pm2_5")
    assert state.state == "4"

    state = hass.states.get("sensor.dormitorio_pm10")
    assert state.state == "3"

    state = hass.states.get("sensor.dormitorio_signal_percentage")
    assert state.state == "76"

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
