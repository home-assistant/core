"""Fixtures for Met weather testing."""
from datetime import datetime
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant.components.met.const import API_URL
import homeassistant.util.dt as dt_util

from tests.common import load_fixture, mock_coro
from tests.test_util.aiohttp import AiohttpClientMocker

NOW = datetime(2016, 6, 9, 1, tzinfo=dt_util.UTC)


@pytest.fixture
def mock_weather():
    """Mock weather data."""
    with patch("homeassistant.components.met.weather.MetWeatherData") as mock_service:
        mock_service = mock_service.return_value
        mock_service.fetching_data.side_effect = lambda: mock_coro(True)
        mock_service.get_current_weather.return_value = {
            "condition": "cloudy",
            "temperature": 15,
            "pressure": 100,
            "humidity": 50,
            "wind_speed": 10,
            "wind_bearing": "NE",
        }
        mock_service.get_forecast.return_value = {}
        yield mock_service


@pytest.fixture
def mock_data(aioclient_mock: AiohttpClientMocker):
    """Mock a successful data."""
    aioclient_mock.get(
        API_URL, text=load_fixture("met.no.xml"),
    )
    with patch("homeassistant.components.met.sensor.dt_util.utcnow", return_value=NOW):
        yield


@pytest.fixture(name="data_failed")
def mock_data_failed(aioclient_mock: AiohttpClientMocker):
    """Mock a failed data."""
    aioclient_mock.get(
        API_URL, exc=aiohttp.ClientError,
    )
