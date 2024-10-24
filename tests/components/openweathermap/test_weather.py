"""Define tests for OpenWeatherMapWeather."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.openweathermap.const import (
    ATTR_API_DATETIME,
    ATTR_API_MINUTE_FORECAST,
    ATTR_API_PRECIPITATION,
    OWM_MODE_V25,
    OWM_MODE_V30,
)
from homeassistant.components.openweathermap.coordinator import WeatherUpdateCoordinator
from homeassistant.components.openweathermap.weather import OpenWeatherMapWeather
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

MOCK_UNIQUE_ID = "mock_unique_id"
MOCK_NAME = "Mock Name"
MOCK_WEATHER_DATA = {
    ATTR_API_MINUTE_FORECAST: [
        {ATTR_API_DATETIME: "2023-10-01T12:00:00Z", ATTR_API_PRECIPITATION: 0},
        {ATTR_API_DATETIME: "2023-10-01T12:01:00Z", ATTR_API_PRECIPITATION: 0.1},
    ],
}


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_coordinator():
    """Create a mock WeatherUpdateCoordinator."""
    coordinator = MagicMock(spec=WeatherUpdateCoordinator)
    coordinator.data = MOCK_WEATHER_DATA
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock OpenweathermapConfigEntry."""
    config_entry = MagicMock()
    config_entry.unique_id = MOCK_UNIQUE_ID
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.name = MOCK_NAME
    config_entry.runtime_data.mode = OWM_MODE_V30
    config_entry.runtime_data.coordinator = MagicMock(spec=WeatherUpdateCoordinator)
    config_entry.runtime_data.coordinator.data = MOCK_WEATHER_DATA
    return config_entry


@pytest.fixture
def mock_add_entities():
    """Create a mock AddEntitiesCallback."""
    return MagicMock(spec=AddEntitiesCallback)


async def test_async_get_minute_forecast(mock_coordinator) -> None:
    """Test the async_get_minute_forecast method."""
    weather = OpenWeatherMapWeather(
        name=MOCK_NAME,
        unique_id=MOCK_UNIQUE_ID,
        mode=OWM_MODE_V30,
        weather_coordinator=mock_coordinator,
    )

    # Test successful minute forecast retrieval
    result = await weather.async_get_minute_forecast()
    assert result == mock_coordinator.data[ATTR_API_MINUTE_FORECAST]

    # Test exception when mode is not OWM_MODE_V30
    weather.mode = OWM_MODE_V25
    with pytest.raises(ServiceValidationError):
        await weather.async_get_minute_forecast()
