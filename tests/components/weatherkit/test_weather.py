"""Weather entity tests for the WeatherKit integration."""

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


async def test_daily_forecast_sums_snowfall_and_precipitation(
    hass: HomeAssistant,
) -> None:
    """Test that snowfallAmount is added to precipitationAmount in daily forecast."""
    with mock_weather_response() as weather_response:
        for day in weather_response["forecastDaily"]["days"]:
            day["snowfallAmount"] = 25.0
            day["precipitationAmount"] = 5.0
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": "weather.home", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    for forecast in response["weather.home"]["forecast"]:
        assert forecast["precipitation"] == 30.0


async def test_hourly_forecast_sums_snowfall_and_precipitation(
    hass: HomeAssistant,
) -> None:
    """Test that snowfallAmount is added to precipitationAmount in hourly forecast."""
    with mock_weather_response() as weather_response:
        for hour in weather_response["forecastHourly"]["hours"]:
            hour["snowfallAmount"] = 12.0
            hour["precipitationAmount"] = 3.0
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": "weather.home", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    for forecast in response["weather.home"]["forecast"]:
        assert forecast["precipitation"] == 15.0


async def test_daily_forecast_snowfall_only(hass: HomeAssistant) -> None:
    """Test daily forecast when only snowfallAmount is present."""
    with mock_weather_response() as weather_response:
        for day in weather_response["forecastDaily"]["days"]:
            day["snowfallAmount"] = 10.0
            day.pop("precipitationAmount", None)
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": "weather.home", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    for forecast in response["weather.home"]["forecast"]:
        assert forecast["precipitation"] == 10.0


async def test_hourly_forecast_snowfall_only(hass: HomeAssistant) -> None:
    """Test hourly forecast when only snowfallAmount is present."""
    with mock_weather_response() as weather_response:
        for hour in weather_response["forecastHourly"]["hours"]:
            hour["snowfallAmount"] = 7.0
            hour.pop("precipitationAmount", None)
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": "weather.home", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    for forecast in response["weather.home"]["forecast"]:
        assert forecast["precipitation"] == 7.0


async def test_daily_forecast_no_precipitation_keys(hass: HomeAssistant) -> None:
    """Test daily forecast returns 0 when both keys are absent."""
    with mock_weather_response() as weather_response:
        for day in weather_response["forecastDaily"]["days"]:
            day.pop("snowfallAmount", None)
            day.pop("precipitationAmount", None)
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": "weather.home", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    for forecast in response["weather.home"]["forecast"]:
        assert forecast["precipitation"] == 0.0


async def test_hourly_forecast_no_precipitation_keys(hass: HomeAssistant) -> None:
    """Test hourly forecast returns 0 when both keys are absent."""
    with mock_weather_response() as weather_response:
        for hour in weather_response["forecastHourly"]["hours"]:
            hour.pop("snowfallAmount", None)
            hour.pop("precipitationAmount", None)
        await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": "weather.home", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    for forecast in response["weather.home"]["forecast"]:
        assert forecast["precipitation"] == 0.0
