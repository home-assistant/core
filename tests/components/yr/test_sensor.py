"""Tests for the Yr sensor platform."""
from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.yr.const import API_URL, CONF_FORECAST, DOMAIN
from homeassistant.const import CONF_NAME, PRESSURE_HPA, TEMP_CELSIUS
import homeassistant.util.dt as dt_util

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

NOW = datetime(2016, 6, 9, 1, tzinfo=dt_util.UTC)


async def setup_component(hass, config):
    """Set up the Yr platform."""

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


@pytest.fixture(name="yr_data")
def mock_controller_data(aioclient_mock: AiohttpClientMocker):
    """Mock a successful data."""
    aioclient_mock.get(
        API_URL, text=load_fixture("yr.no.xml"),
    )
    with patch("homeassistant.components.yr.sensor.dt_util.utcnow", return_value=NOW):
        yield


async def test_default_setup(hass, yr_data):
    """Test the default setup."""
    await setup_component(hass, {})

    assert len(hass.states.async_all()) == 14

    state = hass.states.get("sensor.yr_symbol")
    assert state.state == "3"
    assert state.attributes.get("unit_of_measurement") is None

    state = hass.states.get("sensor.yr_precipitation")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "mm"

    state = hass.states.get("sensor.yr_temperature")
    assert state.state == "28.0"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get("sensor.yr_wind_speed")
    assert state.state == "3.5"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.yr_wind_gust")
    assert state.state == "unknown"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.yr_pressure")
    assert state.state == "1009.3"
    assert state.attributes.get("unit_of_measurement") == PRESSURE_HPA

    state = hass.states.get("sensor.yr_wind_direction")
    assert state.state == "103.6"
    assert state.attributes.get("unit_of_measurement") == "°"

    state = hass.states.get("sensor.yr_humidity")
    assert state.state == "55.5"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_fog")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_cloudiness")
    assert state.state == "100.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_low_clouds")
    assert state.state == "8.6"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_medium_clouds")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_high_clouds")
    assert state.state == "100.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_dewpoint_temperature")
    assert state.state == "18.5"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS


async def test_name_setup(hass, yr_data):
    """Test a custom setup with name."""
    config = {
        CONF_NAME: "Bengbu",
    }
    await setup_component(hass, config)

    assert len(hass.states.async_all()) == 14

    state = hass.states.get("sensor.bengbu_symbol")
    assert state is not None

    state = hass.states.get("sensor.bengbu_precipitation")
    assert state is not None

    state = hass.states.get("sensor.bengbu_temperature")
    assert state is not None

    state = hass.states.get("sensor.bengbu_wind_speed")
    assert state is not None

    state = hass.states.get("sensor.bengbu_wind_gust")
    assert state is not None

    state = hass.states.get("sensor.bengbu_pressure")
    assert state is not None

    state = hass.states.get("sensor.bengbu_wind_direction")
    assert state is not None

    state = hass.states.get("sensor.bengbu_humidity")
    assert state is not None

    state = hass.states.get("sensor.bengbu_fog")
    assert state is not None

    state = hass.states.get("sensor.bengbu_cloudiness")
    assert state is not None

    state = hass.states.get("sensor.bengbu_low_clouds")
    assert state is not None

    state = hass.states.get("sensor.bengbu_medium_clouds")
    assert state is not None

    state = hass.states.get("sensor.bengbu_high_clouds")
    assert state is not None

    state = hass.states.get("sensor.bengbu_dewpoint_temperature")
    assert state is not None


async def test_forecast_setup(hass, yr_data):
    """Test a custom setup with 24h forecast."""
    config = {
        CONF_FORECAST: 24,
    }
    await setup_component(hass, config)

    assert len(hass.states.async_all()) == 14

    state = hass.states.get("sensor.yr_symbol")
    assert state.state == "3"
    assert state.attributes.get("unit_of_measurement") is None

    state = hass.states.get("sensor.yr_precipitation")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "mm"

    state = hass.states.get("sensor.yr_temperature")
    assert state.state == "24.4"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get("sensor.yr_wind_speed")
    assert state.state == "3.6"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.yr_wind_gust")
    assert state.state == "unknown"
    assert state.attributes.get("unit_of_measurement") == "m/s"

    state = hass.states.get("sensor.yr_pressure")
    assert state.state == "1008.3"
    assert state.attributes.get("unit_of_measurement") == PRESSURE_HPA

    state = hass.states.get("sensor.yr_wind_direction")
    assert state.state == "148.9"
    assert state.attributes.get("unit_of_measurement") == "°"

    state = hass.states.get("sensor.yr_humidity")
    assert state.state == "77.4"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_fog")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_cloudiness")
    assert state.state == "75.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_low_clouds")
    assert state.state == "64.1"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_medium_clouds")
    assert state.state == "0.0"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_high_clouds")
    assert state.state == "29.7"
    assert state.attributes.get("unit_of_measurement") == "%"

    state = hass.states.get("sensor.yr_dewpoint_temperature")
    assert state.state == "20.5"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS
