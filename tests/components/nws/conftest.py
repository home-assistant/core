"""Fixtures for National Weather Service tests."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.components.nws.const import DEFAULT_FORECAST, DEFAULT_OBSERVATION


@pytest.fixture()
def mock_simple_nws():
    """Mock pynws SimpleNWS with default values."""
    with patch("homeassistant.components.nws.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.set_station = AsyncMock(return_value=None)
        instance.update_observation = AsyncMock(return_value=None)
        instance.update_forecast = AsyncMock(return_value=None)
        instance.update_forecast_hourly = AsyncMock(return_value=None)
        instance.station = "ABC"
        instance.stations = ["ABC"]
        instance.observation = DEFAULT_OBSERVATION
        instance.forecast = DEFAULT_FORECAST
        instance.forecast_hourly = DEFAULT_FORECAST
        yield mock_nws


@pytest.fixture()
def mock_simple_nws_config():
    """Mock pynws SimpleNWS with default values in config_flow."""
    with patch("homeassistant.components.nws.config_flow.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.set_station = AsyncMock(return_value=None)
        instance.station = "ABC"
        instance.stations = ["ABC"]
        yield mock_nws


@pytest.fixture()
def no_sensor():
    """Remove sensors."""
    with patch(
        "homeassistant.components.nws.sensor.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture()
def no_weather():
    """Remove weather."""
    with patch(
        "homeassistant.components.nws.weather.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
