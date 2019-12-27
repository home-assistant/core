"""Tests for the Met sensor platform."""
from homeassistant import config_entries
from homeassistant.components.met.const import CONF_FORECAST, CONF_TRACK_HOME, DOMAIN
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.helpers.typing import HomeAssistantType


async def setup_component(hass: HomeAssistantType, config):
    """Set up the platform."""

    hass.allow_pool = True
    hass.config.components.add(DOMAIN)
    config_entry = config_entries.ConfigEntry(
        1,
        DOMAIN,
        "Mock Title",
        config,
        "test",
        config_entries.CONN_CLASS_CLOUD_POLL,
        {},
    )
    await hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    # and make sure it completes before going further
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistantType, mock_data):
    """Test a custom setup with name."""
    config = {
        CONF_NAME: "San Diego",
        CONF_LATITUDE: 0,
        CONF_LONGITUDE: 0,
        CONF_ELEVATION: 0,
    }
    await setup_component(hass, config)

    assert len(hass.states.async_all()) == 14

    state = hass.states.get("sensor.san_diego_symbol")
    assert state is not None

    state = hass.states.get("sensor.san_diego_precipitation")
    assert state is not None

    state = hass.states.get("sensor.san_diego_temperature")
    assert state is not None

    state = hass.states.get("sensor.san_diego_wind_speed")
    assert state is not None

    state = hass.states.get("sensor.san_diego_wind_gust")
    assert state is not None

    state = hass.states.get("sensor.san_diego_pressure")
    assert state is not None

    state = hass.states.get("sensor.san_diego_wind_direction")
    assert state is not None

    state = hass.states.get("sensor.san_diego_humidity")
    assert state is not None

    state = hass.states.get("sensor.san_diego_fog")
    assert state is not None

    state = hass.states.get("sensor.san_diego_cloudiness")
    assert state is not None

    state = hass.states.get("sensor.san_diego_low_clouds")
    assert state is not None

    state = hass.states.get("sensor.san_diego_medium_clouds")
    assert state is not None

    state = hass.states.get("sensor.san_diego_high_clouds")
    assert state is not None

    state = hass.states.get("sensor.san_diego_dewpoint_temperature")
    assert state is not None


async def test_track_home_setup(hass: HomeAssistantType, mock_data):
    """Test the track_home setup."""
    await setup_component(hass, {CONF_TRACK_HOME: True})

    assert len(hass.states.async_all()) == 14

    state = hass.states.get("sensor.met_symbol")
    assert state.state == "3"
    assert state.attributes.get("unit_of_measurement") is None

    state = hass.states.get("sensor.met_precipitation")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "mm"

    state = hass.states.get("sensor.met_temperature")
    assert state.state == "28.0"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get("sensor.met_wind_speed")
    assert state.state == "3.5"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.met_wind_gust")
    assert state.state == "unknown"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.met_pressure")
    assert state.state == "1009.3"
    assert state.attributes.get("unit_of_measurement") == PRESSURE_HPA

    state = hass.states.get("sensor.met_wind_direction")
    assert state.state == "103.6"
    assert state.attributes.get("unit_of_measurement") == "°"

    state = hass.states.get("sensor.met_humidity")
    assert state.state == "55.5"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_fog")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_cloudiness")
    assert state.state == "100.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_low_clouds")
    assert state.state == "8.6"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_medium_clouds")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_high_clouds")
    assert state.state == "100.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_dewpoint_temperature")
    assert state.state == "18.5"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS


async def test_forecast_setup(hass: HomeAssistantType, mock_data):
    """Test a custom setup with 24h forecast."""
    config = {
        CONF_TRACK_HOME: True,
        CONF_FORECAST: 24,
    }
    await setup_component(hass, config)

    assert len(hass.states.async_all()) == 14

    state = hass.states.get("sensor.met_symbol")
    assert state.state == "3"
    assert state.attributes.get("unit_of_measurement") is None

    state = hass.states.get("sensor.met_precipitation")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "mm"

    state = hass.states.get("sensor.met_temperature")
    assert state.state == "24.4"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get("sensor.met_wind_speed")
    assert state.state == "3.6"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.met_wind_gust")
    assert state.state == "unknown"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.met_pressure")
    assert state.state == "1008.3"
    assert state.attributes.get("unit_of_measurement") == PRESSURE_HPA

    state = hass.states.get("sensor.met_wind_direction")
    assert state.state == "148.9"
    assert state.attributes.get("unit_of_measurement") == "°"

    state = hass.states.get("sensor.met_humidity")
    assert state.state == "77.4"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_fog")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_cloudiness")
    assert state.state == "75.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_low_clouds")
    assert state.state == "64.1"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_medium_clouds")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_high_clouds")
    assert state.state == "29.7"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.met_dewpoint_temperature")
    assert state.state == "20.5"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS
