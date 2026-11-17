"""Weather entity tests for the WeatherKit integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    WeatherEntityFeature,
    WeatherEntityStateAttribute,
    WeatherService,
)
from homeassistant.components.weatherkit.const import ATTRIBUTION
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant

from . import init_integration, mock_weather_response


async def test_current_weather(hass: HomeAssistant) -> None:
    """Test states of the current weather."""
    with mock_weather_response():
        await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state
    assert state.state == "partlycloudy"
    assert state.attributes[WeatherEntityStateAttribute.HUMIDITY] == 91
    assert state.attributes[WeatherEntityStateAttribute.PRESSURE] == 1009.8
    assert state.attributes[WeatherEntityStateAttribute.TEMPERATURE] == 22.9
    assert state.attributes[WeatherEntityStateAttribute.VISIBILITY] == 20.97
    assert state.attributes[WeatherEntityStateAttribute.WIND_BEARING] == 259
    assert state.attributes[WeatherEntityStateAttribute.WIND_SPEED] == 5.23
    assert state.attributes[WeatherEntityStateAttribute.APPARENT_TEMPERATURE] == 24.9
    assert state.attributes[WeatherEntityStateAttribute.DEW_POINT] == 21.3
    assert state.attributes[WeatherEntityStateAttribute.CLOUD_COVERAGE] == 62
    assert state.attributes[WeatherEntityStateAttribute.WIND_GUST_SPEED] == 10.53
    assert state.attributes[WeatherEntityStateAttribute.UV_INDEX] == 1
    assert state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION


async def test_current_weather_nighttime(hass: HomeAssistant) -> None:
    """Test that the condition is clear-night when it's sunny and night time."""
    with mock_weather_response(is_night_time=True):
        await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state
    assert state.state == "clear-night"


async def test_daily_forecast_missing(hass: HomeAssistant) -> None:
    """Test that daily forecast is not supported when WeatherKit doesn't support it."""
    with mock_weather_response(has_daily_forecast=False):
        await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] & WeatherEntityFeature.FORECAST_DAILY
    ) == 0


async def test_hourly_forecast_missing(hass: HomeAssistant) -> None:
    """Test that hourly forecast is not supported when WeatherKit doesn't support it."""
    with mock_weather_response(has_hourly_forecast=False):
        await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] & WeatherEntityFeature.FORECAST_HOURLY
    ) == 0


@pytest.mark.parametrize(
    ("service"),
    [WeatherService.GET_FORECASTS],
)
async def test_hourly_forecast(
    hass: HomeAssistant, snapshot: SnapshotAssertion, service: str
) -> None:
    """Test states of the hourly forecast."""
    with mock_weather_response():
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.home",
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("service"),
    [WeatherService.GET_FORECASTS],
)
async def test_daily_forecast(
    hass: HomeAssistant, snapshot: SnapshotAssertion, service: str
) -> None:
    """Test states of the daily forecast."""
    with mock_weather_response():
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.home",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
