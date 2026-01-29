"""Tests for Garmin Connect init."""

from unittest.mock import AsyncMock, patch

from aiogarmin import GarminAuthError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup."""
    mock_config_entry.add_to_hass(hass)

    mock_data = {
        "totalSteps": 10000,
        "totalDistance": 8000.0,
        "activeCalories": 500,
        "restingHeartRate": 60,
        "minHeartRate": 50,
        "maxHeartRate": 150,
        "averageStressLevel": 30,
        "bodyBatteryChargedValue": 80,
        "bodyBatteryDrainedValue": 20,
        "floorsAscended": 10,
        "dailyStepGoal": 10000,
    }

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auth failure during setup."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class:
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = None
        mock_auth.refresh_tokens = AsyncMock(side_effect=GarminAuthError("Auth failed"))

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading."""
    mock_config_entry.add_to_hass(hass)

    mock_data = {
        "totalSteps": 10000,
        "totalDistance": 8000.0,
        "activeCalories": 500,
        "restingHeartRate": 60,
        "dailyStepGoal": 10000,
    }

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
