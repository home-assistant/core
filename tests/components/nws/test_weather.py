"""Tests for the NWS weather component."""
from homeassistant.components.nws.weather import ATTR_FORECAST_PRECIP_PROB
from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_PA,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.common import assert_setup_component, load_fixture

EXP_OBS_IMP = {
    ATTR_WEATHER_TEMPERATURE: round(
        convert_temperature(26.7, TEMP_CELSIUS, TEMP_FAHRENHEIT)
    ),
    ATTR_WEATHER_WIND_BEARING: 190,
    ATTR_WEATHER_WIND_SPEED: round(
        convert_distance(2.6, LENGTH_METERS, LENGTH_MILES) * 3600
    ),
    ATTR_WEATHER_PRESSURE: round(
        convert_pressure(101040, PRESSURE_PA, PRESSURE_INHG), 2
    ),
    ATTR_WEATHER_VISIBILITY: round(
        convert_distance(16090, LENGTH_METERS, LENGTH_MILES)
    ),
    ATTR_WEATHER_HUMIDITY: 64,
}

EXP_OBS_METR = {
    ATTR_WEATHER_TEMPERATURE: round(26.7),
    ATTR_WEATHER_WIND_BEARING: 190,
    ATTR_WEATHER_WIND_SPEED: round(
        convert_distance(2.6, LENGTH_METERS, LENGTH_KILOMETERS) * 3600
    ),
    ATTR_WEATHER_PRESSURE: round(convert_pressure(101040, PRESSURE_PA, PRESSURE_HPA)),
    ATTR_WEATHER_VISIBILITY: round(
        convert_distance(16090, LENGTH_METERS, LENGTH_KILOMETERS)
    ),
    ATTR_WEATHER_HUMIDITY: 64,
}

EXP_FORE_IMP = {
    ATTR_FORECAST_CONDITION: "lightning-rainy",
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: 70,
    ATTR_FORECAST_WIND_SPEED: 10,
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIP_PROB: 90,
}

EXP_FORE_METR = {
    ATTR_FORECAST_CONDITION: "lightning-rainy",
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: round(convert_temperature(70, TEMP_FAHRENHEIT, TEMP_CELSIUS)),
    ATTR_FORECAST_WIND_SPEED: round(
        convert_distance(10, LENGTH_MILES, LENGTH_KILOMETERS)
    ),
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIP_PROB: 90,
}


MINIMAL_CONFIG = {
    "weather": {
        "platform": "nws",
        "api_key": "x@example.com",
        "latitude": 40.0,
        "longitude": -85.0,
    }
}

INVALID_CONFIG = {
    "weather": {"platform": "nws", "api_key": "x@example.com", "latitude": 40.0}
}

STAURL = "https://api.weather.gov/points/{},{}/stations"
OBSURL = "https://api.weather.gov/stations/{}/observations/"
FORCURL = "https://api.weather.gov/points/{},{}/forecast"


async def test_imperial(hass, aioclient_mock):
    """Test with imperial units."""
    aioclient_mock.get(
        STAURL.format(40.0, -85.0), text=load_fixture("nws-weather-sta-valid.json")
    )
    aioclient_mock.get(
        OBSURL.format("KMIE"), text=load_fixture("nws-weather-obs-valid.json")
    )
    aioclient_mock.get(
        FORCURL.format(40.0, -85.0), text=load_fixture("nws-weather-fore-valid.json")
    )

    hass.config.units = IMPERIAL_SYSTEM

    with assert_setup_component(1, "weather"):
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.kmie")
    assert state
    assert state.state == "sunny"

    data = state.attributes
    for key, value in EXP_OBS_IMP.items():
        assert data.get(key) == value
    assert state.attributes.get("friendly_name") == "KMIE"
    forecast = data.get(ATTR_FORECAST)
    for key, value in EXP_FORE_IMP.items():
        assert forecast[0].get(key) == value


async def test_metric(hass, aioclient_mock):
    """Test with metric units."""
    aioclient_mock.get(
        STAURL.format(40.0, -85.0), text=load_fixture("nws-weather-sta-valid.json")
    )
    aioclient_mock.get(
        OBSURL.format("KMIE"), text=load_fixture("nws-weather-obs-valid.json")
    )
    aioclient_mock.get(
        FORCURL.format(40.0, -85.0), text=load_fixture("nws-weather-fore-valid.json")
    )

    hass.config.units = METRIC_SYSTEM

    with assert_setup_component(1, "weather"):
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.kmie")
    assert state
    assert state.state == "sunny"

    data = state.attributes
    for key, value in EXP_OBS_METR.items():
        assert data.get(key) == value
    assert state.attributes.get("friendly_name") == "KMIE"
    forecast = data.get(ATTR_FORECAST)
    for key, value in EXP_FORE_METR.items():
        assert forecast[0].get(key) == value


async def test_none(hass, aioclient_mock):
    """Test with imperial units."""
    aioclient_mock.get(
        STAURL.format(40.0, -85.0), text=load_fixture("nws-weather-sta-valid.json")
    )
    aioclient_mock.get(
        OBSURL.format("KMIE"), text=load_fixture("nws-weather-obs-null.json")
    )
    aioclient_mock.get(
        FORCURL.format(40.0, -85.0), text=load_fixture("nws-weather-fore-null.json")
    )

    hass.config.units = IMPERIAL_SYSTEM

    with assert_setup_component(1, "weather"):
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.kmie")
    assert state
    assert state.state == "unknown"

    data = state.attributes
    for key in EXP_OBS_IMP:
        assert data.get(key) is None
    assert state.attributes.get("friendly_name") == "KMIE"
    forecast = data.get(ATTR_FORECAST)
    for key in EXP_FORE_IMP:
        assert forecast[0].get(key) is None


async def test_fail_obs(hass, aioclient_mock):
    """Test failing observation/forecast update."""
    aioclient_mock.get(
        STAURL.format(40.0, -85.0), text=load_fixture("nws-weather-sta-valid.json")
    )
    aioclient_mock.get(
        OBSURL.format("KMIE"),
        text=load_fixture("nws-weather-obs-valid.json"),
        status=400,
    )
    aioclient_mock.get(
        FORCURL.format(40.0, -85.0),
        text=load_fixture("nws-weather-fore-valid.json"),
        status=400,
    )

    hass.config.units = IMPERIAL_SYSTEM

    with assert_setup_component(1, "weather"):
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.kmie")
    assert state


async def test_fail_stn(hass, aioclient_mock):
    """Test failing station update."""
    aioclient_mock.get(
        STAURL.format(40.0, -85.0),
        text=load_fixture("nws-weather-sta-valid.json"),
        status=400,
    )
    aioclient_mock.get(
        OBSURL.format("KMIE"), text=load_fixture("nws-weather-obs-valid.json")
    )
    aioclient_mock.get(
        FORCURL.format(40.0, -85.0), text=load_fixture("nws-weather-fore-valid.json")
    )

    hass.config.units = IMPERIAL_SYSTEM

    with assert_setup_component(1, "weather"):
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.kmie")
    assert state is None


async def test_invalid_config(hass, aioclient_mock):
    """Test invalid config.."""
    aioclient_mock.get(
        STAURL.format(40.0, -85.0), text=load_fixture("nws-weather-sta-valid.json")
    )
    aioclient_mock.get(
        OBSURL.format("KMIE"), text=load_fixture("nws-weather-obs-valid.json")
    )
    aioclient_mock.get(
        FORCURL.format(40.0, -85.0), text=load_fixture("nws-weather-fore-valid.json")
    )

    hass.config.units = IMPERIAL_SYSTEM

    with assert_setup_component(0, "weather"):
        await async_setup_component(hass, "weather", INVALID_CONFIG)

    state = hass.states.get("weather.kmie")
    assert state is None
