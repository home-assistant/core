"""Fixtures for National Weather Service tests."""
import pytest

from tests.async_mock import AsyncMock, patch
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
