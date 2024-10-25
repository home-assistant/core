"""Test the OpenWeatherMap weather entity."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.openweathermap.const import (
    ATTR_API_MINUTE_FORECAST,
    DOMAIN,
    OWM_MODE_V25,
    OWM_MODE_V30,
)
from homeassistant.components.openweathermap.weather import SERVICE_GET_MINUTE_FORECAST
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock OpenWeatherMap config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key",
            CONF_LATITUDE: 12.34,
            CONF_LONGITUDE: 56.78,
            CONF_MODE: OWM_MODE_V30,
            CONF_NAME: "OpenWeatherMap",
        },
        unique_id="test_unique_id",
    )


@pytest.fixture
def mock_weather_data():
    """Return mock weather data."""
    return {
        ATTR_API_MINUTE_FORECAST: [
            {"time": "2024-10-01T12:00:00Z", "precipitation": 0},
            {"time": "2024-10-01T12:01:00Z", "precipitation": 0.1},
            {"time": "2024-10-01T12:02:00Z", "precipitation": 0.23},
            {"time": "2024-10-01T12:03:00Z", "precipitation": 0},
        ]
    }


@pytest.fixture(autouse=True)
def mock_weather_update():
    """Mock the WeatherUpdateCoordinator to prevent API calls."""
    with patch(
        "homeassistant.components.openweathermap.coordinator.WeatherUpdateCoordinator._async_update_data",
        new=AsyncMock(),
    ) as mock_update:
        yield mock_update


@pytest.mark.asyncio
async def test_minute_forecast(
    hass: HomeAssistant,
    mock_config_entry,
    mock_weather_data,
    mock_weather_update,
) -> None:
    """Test the OpenWeatherMapWeather Minute forecast."""
    # Set up the mock data to be returned by the coordinator
    mock_weather_update.return_value = mock_weather_data

    # Add the MockConfigEntry to hass
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the entry is loaded
    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Get the entity registry and verify the entity is registered
    entity_registry = er.async_get(hass)
    entity_id = "weather.openweathermap"
    entry = entity_registry.async_get(entity_id)
    assert entry is not None

    # Test the async_get_minute_forecast service
    # We can call the service and assert the result
    with patch(
        "homeassistant.components.openweathermap.weather.OpenWeatherMapWeather.async_get_minute_forecast",
        return_value=mock_weather_data[ATTR_API_MINUTE_FORECAST],
    ):
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MINUTE_FORECAST,
            {"entity_id": entity_id},
            blocking=True,
            return_response=True,
        )
        assert result == {
            "weather.openweathermap": mock_weather_data[ATTR_API_MINUTE_FORECAST]
        }

    # Test exception when mode is not OWM_MODE_V30
    # Update the config entry data to change the mode
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_MODE: OWM_MODE_V25}
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Try calling the service again and expect a ServiceValidationError
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MINUTE_FORECAST,
            {"entity_id": entity_id},
            blocking=True,
            return_response=True,
        )

    # Cleanup
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
