"""Tests for the NWS weather component."""
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant.components.weather import ATTR_FORECAST
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from .const import (
    DEFAULT_FORECAST,
    DEFAULT_OBSERVATION,
    EXPECTED_FORECAST_IMPERIAL,
    EXPECTED_FORECAST_METRIC,
    EXPECTED_OBSERVATION_IMPERIAL,
    EXPECTED_OBSERVATION_METRIC,
    NONE_FORECAST,
    NONE_OBSERVATION,
)

from tests.common import mock_coro

MINIMAL_CONFIG = {
    "weather": {
        "platform": "nws",
        "api_key": "x@example.com",
        "latitude": 40.0,
        "longitude": -85.0,
    }
}

HOURLY_CONFIG = {
    "weather": {
        "platform": "nws",
        "api_key": "x@example.com",
        "latitude": 40.0,
        "longitude": -85.0,
        "mode": "hourly",
    }
}


@pytest.mark.parametrize(
    "units,result_observation,result_forecast",
    [
        (IMPERIAL_SYSTEM, EXPECTED_OBSERVATION_IMPERIAL, EXPECTED_FORECAST_IMPERIAL),
        (METRIC_SYSTEM, EXPECTED_OBSERVATION_METRIC, EXPECTED_FORECAST_METRIC),
    ],
)
async def test_imperial_metric(hass, units, result_observation, result_forecast):
    """Test with imperial and metric units."""
    hass.config.units = units
    with patch("homeassistant.components.nws.weather.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.station = "ABC"
        instance.set_station.return_value = mock_coro()
        instance.update_observation.return_value = mock_coro()
        instance.update_forecast.return_value = mock_coro()
        instance.observation = DEFAULT_OBSERVATION
        instance.forecast = DEFAULT_FORECAST

        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.abc")
    assert state
    assert state.state == "sunny"

    data = state.attributes
    for key, value in result_observation.items():
        assert data.get(key) == value

    forecast = data.get(ATTR_FORECAST)
    for key, value in result_forecast.items():
        assert forecast[0].get(key) == value


async def test_hourly(hass):
    """Test with hourly option."""
    hass.config.units = IMPERIAL_SYSTEM

    with patch("homeassistant.components.nws.weather.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.station = "ABC"
        instance.set_station.return_value = mock_coro()
        instance.update_observation.return_value = mock_coro()
        instance.update_forecast_hourly.return_value = mock_coro()
        instance.observation = DEFAULT_OBSERVATION
        instance.forecast_hourly = DEFAULT_FORECAST

        await async_setup_component(hass, "weather", HOURLY_CONFIG)

    state = hass.states.get("weather.abc")
    assert state
    assert state.state == "sunny"

    data = state.attributes
    for key, value in EXPECTED_OBSERVATION_IMPERIAL.items():
        assert data.get(key) == value

    forecast = data.get(ATTR_FORECAST)
    for key, value in EXPECTED_FORECAST_IMPERIAL.items():
        assert forecast[0].get(key) == value


async def test_none_values(hass):
    """Test with none values in observation and forecast dicts."""
    with patch("homeassistant.components.nws.weather.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.station = "ABC"
        instance.set_station.return_value = mock_coro()
        instance.update_observation.return_value = mock_coro()
        instance.update_forecast.return_value = mock_coro()
        instance.observation = NONE_OBSERVATION
        instance.forecast = NONE_FORECAST
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.abc")
    assert state
    assert state.state == "unknown"

    data = state.attributes
    for key in EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None

    forecast = data.get(ATTR_FORECAST)
    for key in EXPECTED_FORECAST_IMPERIAL:
        assert forecast[0].get(key) is None


async def test_none(hass):
    """Test with None as observation and forecast."""
    with patch("homeassistant.components.nws.weather.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.station = "ABC"
        instance.set_station.return_value = mock_coro()
        instance.update_observation.return_value = mock_coro()
        instance.update_forecast.return_value = mock_coro()
        instance.observation = None
        instance.forecast = None
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    state = hass.states.get("weather.abc")
    assert state
    assert state.state == "unknown"

    data = state.attributes
    for key in EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None

    forecast = data.get(ATTR_FORECAST)
    assert forecast is None


async def test_error_station(hass):
    """Test error in setting station."""
    with patch("homeassistant.components.nws.weather.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.station = "ABC"
        instance.set_station.side_effect = aiohttp.ClientError
        instance.update_observation.return_value = mock_coro()
        instance.update_forecast.return_value = mock_coro()
        instance.observation = None
        instance.forecast = None
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

        state = hass.states.get("weather.abc")
        assert state is None


async def test_error_observation(hass, caplog):
    """Test error during update observation."""
    with patch("homeassistant.components.nws.weather.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.station = "ABC"
        instance.set_station.return_value = mock_coro()
        instance.update_observation.side_effect = aiohttp.ClientError
        instance.update_forecast.return_value = mock_coro()
        instance.observation = None
        instance.forecast = None
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)

    assert "Error updating observation from station ABC" in caplog.text


async def test_error_forecast(hass, caplog):
    """Test error during update forecast."""
    with patch("homeassistant.components.nws.weather.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.station = "ABC"
        instance.set_station.return_value = mock_coro()
        instance.update_observation.return_value = mock_coro()
        instance.update_forecast.side_effect = aiohttp.ClientError
        instance.observation = None
        instance.forecast = None
        await async_setup_component(hass, "weather", MINIMAL_CONFIG)
        assert "Error updating forecast from station ABC" in caplog.text
