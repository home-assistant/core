"""Test init of Google Weather integration."""

from unittest.mock import AsyncMock

from google_weather_api import GoogleWeatherApiError

from homeassistant.components.google_weather.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test a successful setup entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("weather.home")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"


async def test_config_not_ready_current_conditions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test for setup failure if async_get_current_conditions fails."""
    mock_google_weather_api.async_get_current_conditions.side_effect = (
        GoogleWeatherApiError()
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_not_ready_daily_forecast(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test for setup failure if async_get_daily_forecast fails."""
    mock_google_weather_api.async_get_daily_forecast.side_effect = (
        GoogleWeatherApiError()
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_not_ready_hourly_forecast(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test for setup failure if async_get_hourly_forecast fails."""
    mock_google_weather_api.async_get_hourly_forecast.side_effect = (
        GoogleWeatherApiError()
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test successful unload of entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
