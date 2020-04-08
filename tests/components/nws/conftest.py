"""Fixtures for National Weather Service tests."""
from unittest.mock import patch

import pytest

from tests.common import mock_coro
from tests.components.nws.const import DEFAULT_FORECAST, DEFAULT_OBSERVATION


@pytest.fixture()
def mock_simple_nws():
    """Mock pynws SimpleNWS with default values."""
    with patch("homeassistant.components.nws.SimpleNWS") as mock_nws:
        instance = mock_nws.return_value
        instance.set_station.return_value = mock_coro()
        instance.update_observation.return_value = mock_coro()
        instance.update_forecast.return_value = mock_coro()
        instance.update_forecast_hourly.return_value = mock_coro()
        instance.station = "ABC"
        instance.stations = ["ABC"]
        instance.observation = DEFAULT_OBSERVATION
        instance.forecast = DEFAULT_FORECAST
        instance.forecast_hourly = DEFAULT_FORECAST
        yield mock_nws
