"""The tests for the Yr sensor platform."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.const import SPEED_METERS_PER_SECOND, UNIT_PERCENTAGE
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, load_fixture

NOW = datetime(2016, 6, 9, 1, tzinfo=dt_util.UTC)


async def test_default_setup(hass, aioclient_mock):
    """Test the default setup."""
    aioclient_mock.get(
        "https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/",
        text=load_fixture("yr.no.xml"),
    )
    config = {"platform": "yr", "elevation": 0}
    hass.allow_pool = True
    with patch(
        "homeassistant.components.yr.sensor.dt_util.utcnow", return_value=NOW
    ), assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

    state = hass.states.get("sensor.yr_symbol")

    assert state.state == "3"
    assert state.attributes.get("unit_of_measurement") is None


async def test_custom_setup(hass, aioclient_mock):
    """Test a custom setup."""
    aioclient_mock.get(
        "https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/",
        text=load_fixture("yr.no.xml"),
    )

    config = {
        "platform": "yr",
        "elevation": 0,
        "monitored_conditions": [
            "pressure",
            "windDirection",
            "humidity",
            "fog",
            "windSpeed",
        ],
    }
    hass.allow_pool = True
    with patch(
        "homeassistant.components.yr.sensor.dt_util.utcnow", return_value=NOW
    ), assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

    state = hass.states.get("sensor.yr_pressure")
    assert state.attributes.get("unit_of_measurement") == "hPa"
    assert state.state == "1009.3"

    state = hass.states.get("sensor.yr_wind_direction")
    assert state.attributes.get("unit_of_measurement") == "°"
    assert state.state == "103.6"

    state = hass.states.get("sensor.yr_humidity")
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE
    assert state.state == "55.5"

    state = hass.states.get("sensor.yr_fog")
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE
    assert state.state == "0.0"

    state = hass.states.get("sensor.yr_wind_speed")
    assert state.attributes.get("unit_of_measurement") == SPEED_METERS_PER_SECOND
    assert state.state == "3.5"


async def test_forecast_setup(hass, aioclient_mock):
    """Test a custom setup with 24h forecast."""
    aioclient_mock.get(
        "https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/",
        text=load_fixture("yr.no.xml"),
    )

    config = {
        "platform": "yr",
        "elevation": 0,
        "forecast": 24,
        "monitored_conditions": [
            "pressure",
            "windDirection",
            "humidity",
            "fog",
            "windSpeed",
        ],
    }
    hass.allow_pool = True
    with patch(
        "homeassistant.components.yr.sensor.dt_util.utcnow", return_value=NOW
    ), assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

    state = hass.states.get("sensor.yr_pressure")
    assert state.attributes.get("unit_of_measurement") == "hPa"
    assert state.state == "1008.3"

    state = hass.states.get("sensor.yr_wind_direction")
    assert state.attributes.get("unit_of_measurement") == "°"
    assert state.state == "148.9"

    state = hass.states.get("sensor.yr_humidity")
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE
    assert state.state == "77.4"

    state = hass.states.get("sensor.yr_fog")
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE
    assert state.state == "0.0"

    state = hass.states.get("sensor.yr_wind_speed")
    assert state.attributes.get("unit_of_measurement") == SPEED_METERS_PER_SECOND
    assert state.state == "3.6"
