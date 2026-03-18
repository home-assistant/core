"""Test init of Google Weather integration."""

from unittest.mock import AsyncMock

from google_weather_api import GoogleWeatherApiError
import pytest

from homeassistant.components.google_weather.const import DOMAIN
from homeassistant.components.google_weather.coordinator import (
    GoogleWeatherCurrentConditionsCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

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


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test that the coordinator raises UpdateFailed with the correct translation key."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    subentry_id = list(mock_config_entry.subentries.keys())[0]
    coordinator: GoogleWeatherCurrentConditionsCoordinator = (
        mock_config_entry.runtime_data.subentries_runtime_data[
            subentry_id
        ].coordinator_observation
    )

    mock_google_weather_api.async_get_current_conditions.side_effect = (
        GoogleWeatherApiError("API error")
    )

    await coordinator.async_refresh()

    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == "update_error"
    assert coordinator.last_exception.translation_placeholders == {
        "data_type_name": "current weather conditions",
        "error": "API error",
    }


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
