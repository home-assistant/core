"""Fixtures for Met weather testing."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_weather():
    """Mock weather data."""
    with patch("metno.MetWeatherData") as mock_data:
        mock_data = mock_data.return_value
        mock_data.fetching_data = AsyncMock(return_value=True)
        mock_data.get_current_weather.return_value = {
            "condition": "cloudy",
            "temperature": 15,
            "pressure": 100,
            "humidity": 50,
            "wind_speed": 10,
            "wind_bearing": "NE",
            "dew_point": 12.1,
        }
        mock_data.get_forecast.return_value = {}
        yield mock_data
