"""Weather entity tests for the WeatherKit integration."""

from typing import Any

import pytest
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
    SERVICE_GET_FORECASTS,
    WeatherEntityFeature,
)
from homeassistant.components.weatherkit.const import ATTRIBUTION
from homeassistant.components.weatherkit.weather import (
    _map_daily_forecast,
    _map_hourly_forecast,
)
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
    [SERVICE_GET_FORECASTS],
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
    [SERVICE_GET_FORECASTS],
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


def _daily_forecast_data(**overrides: Any) -> dict[str, Any]:
    """Return a minimal daily forecast dict with optional overrides."""
    base: dict[str, Any] = {
        "forecastStart": "2023-12-01T07:00:00Z",
        "conditionCode": "Snow",
        "temperatureMax": -2.0,
        "temperatureMin": -10.0,
        "precipitationAmount": 5.0,
        "precipitationChance": 0.8,
        "snowfallAmount": 0.0,
        "maxUvIndex": 2,
    }
    base.update(overrides)
    return base


def _hourly_forecast_data(**overrides: Any) -> dict[str, Any]:
    """Return a minimal hourly forecast dict with optional overrides."""
    base: dict[str, Any] = {
        "forecastStart": "2023-12-01T08:00:00Z",
        "conditionCode": "Snow",
        "temperature": -5.0,
        "temperatureApparent": -8.0,
        "temperatureDewPoint": -6.0,
        "pressure": 1015.0,
        "windGust": 20.0,
        "windSpeed": 10.0,
        "windDirection": 180,
        "humidity": 0.85,
        "precipitationAmount": 3.0,
        "precipitationChance": 0.7,
        "snowfallAmount": 0.0,
        "cloudCover": 0.9,
        "uvIndex": 1,
    }
    base.update(overrides)
    return base


def test_daily_forecast_sums_snowfall_and_precipitation() -> None:
    """Test that snowfallAmount is added to precipitationAmount."""
    forecast = _daily_forecast_data(snowfallAmount=25.0, precipitationAmount=5.0)
    result = _map_daily_forecast(forecast)
    assert result["native_precipitation"] == 30.0


def test_daily_forecast_precipitation_only_when_no_snowfall() -> None:
    """Test that result equals precipitationAmount when snowfallAmount is zero."""
    forecast = _daily_forecast_data(snowfallAmount=0.0, precipitationAmount=5.0)
    result = _map_daily_forecast(forecast)
    assert result["native_precipitation"] == 5.0


def test_hourly_forecast_sums_snowfall_and_precipitation() -> None:
    """Test that snowfallAmount is added to precipitationAmount."""
    forecast = _hourly_forecast_data(snowfallAmount=12.0, precipitationAmount=3.0)
    result = _map_hourly_forecast(forecast)
    assert result["native_precipitation"] == 15.0


def test_hourly_forecast_precipitation_only_when_no_snowfall() -> None:
    """Test that result equals precipitationAmount when snowfallAmount is zero."""
    forecast = _hourly_forecast_data(snowfallAmount=0.0, precipitationAmount=3.0)
    result = _map_hourly_forecast(forecast)
    assert result["native_precipitation"] == 3.0
