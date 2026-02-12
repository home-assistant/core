"""Test init of Google Weather integration."""

from unittest.mock import AsyncMock

from google_weather_api import GoogleWeatherApiError
import pytest

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


@pytest.mark.parametrize(
    "failing_api_method",
    [
        "async_get_current_conditions",
        "async_get_daily_forecast",
        "async_get_hourly_forecast",
    ],
)
async def test_config_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
    failing_api_method: str,
) -> None:
    """Test for setup failure if an API call fails."""
    getattr(
        mock_google_weather_api, failing_api_method
    ).side_effect = GoogleWeatherApiError()

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
