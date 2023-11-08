"""Weather entity tests for the WeatherKit integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_UV_INDEX,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECAST,
)
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.components.weatherkit.const import ATTRIBUTION
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_current_weather(hass: HomeAssistant) -> None:
    """Test states of the current weather."""
    await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state
    assert state.state == "partlycloudy"
    assert state.attributes[ATTR_WEATHER_HUMIDITY] == 91
    assert state.attributes[ATTR_WEATHER_PRESSURE] == 1009.8
    assert state.attributes[ATTR_WEATHER_TEMPERATURE] == 22.9
    assert state.attributes[ATTR_WEATHER_VISIBILITY] == 20.97
    assert state.attributes[ATTR_WEATHER_WIND_BEARING] == 259
    assert state.attributes[ATTR_WEATHER_WIND_SPEED] == 5.23
    assert state.attributes[ATTR_WEATHER_APPARENT_TEMPERATURE] == 24.9
    assert state.attributes[ATTR_WEATHER_DEW_POINT] == 21.3
    assert state.attributes[ATTR_WEATHER_CLOUD_COVERAGE] == 62
    assert state.attributes[ATTR_WEATHER_WIND_GUST_SPEED] == 10.53
    assert state.attributes[ATTR_WEATHER_UV_INDEX] == 1
    assert state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION


async def test_current_weather_nighttime(hass: HomeAssistant) -> None:
    """Test that the condition is clear-night when it's sunny and night time."""
    await init_integration(hass, is_night_time=True)

    state = hass.states.get("weather.home")
    assert state
    assert state.state == "clear-night"


async def test_daily_forecast_missing(hass: HomeAssistant) -> None:
    """Test that daily forecast is not supported when WeatherKit doesn't support it."""
    await init_integration(hass, has_daily_forecast=False)

    state = hass.states.get("weather.home")
    assert state
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] & WeatherEntityFeature.FORECAST_DAILY
    ) == 0


async def test_hourly_forecast_missing(hass: HomeAssistant) -> None:
    """Test that hourly forecast is not supported when WeatherKit doesn't support it."""
    await init_integration(hass, has_hourly_forecast=False)

    state = hass.states.get("weather.home")
    assert state
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] & WeatherEntityFeature.FORECAST_HOURLY
    ) == 0


async def test_hourly_forecast(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test states of the hourly forecast."""
    await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {
            "entity_id": "weather.home",
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response["forecast"] != []
    assert response == snapshot


async def test_daily_forecast(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test states of the daily forecast."""
    await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {
            "entity_id": "weather.home",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response["forecast"] != []
    assert response == snapshot
