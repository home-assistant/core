"""Fixtures for Met Éireann weather testing."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_weather():
    """Mock weather data."""
    with patch("meteireann.WeatherData") as mock_data:
        mock_data = mock_data.return_value
        mock_data.fetching_data = AsyncMock(return_value=True)
        mock_data.get_current_weather.return_value = {
            "condition": "Cloud",
            "temperature": 15,
            "pressure": 100,
            "humidity": 50,
            "wind_speed": 10,
            "wind_bearing": "NE",
        }
        mock_data.get_forecast.return_value = {}
        yield mock_data
