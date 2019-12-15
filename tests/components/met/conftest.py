"""Fixtures for Met weather testing."""
from unittest.mock import patch

import pytest

from tests.common import mock_coro


@pytest.fixture
def mock_weather():
    """Mock weather data."""
    with patch("metno.MetWeatherData") as mock_data:
        mock_data = mock_data.return_value
        mock_data.fetching_data.side_effect = lambda: mock_coro(True)
        mock_data.get_current_weather.return_value = {
            "condition": "cloudy",
            "temperature": 15,
            "pressure": 100,
            "humidity": 50,
            "wind_speed": 10,
            "wind_bearing": "NE",
        }
        mock_data.get_forecast.return_value = {}
        yield mock_data
