"""Test the Hisense ConnectLife integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hisense_connectlife import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry."""
    with (
        patch(
            "homeassistant.components.hisense_connectlife.HisenseACPluginDataUpdateCoordinator"
        ) as mock_coord_class,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_impl,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_oauth2_session_class,
        patch("aiohttp.ClientSession") as mock_client_session,
    ):
        mock_coordinator = AsyncMock()
        mock_coordinator.async_setup = AsyncMock(return_value=True)
        mock_coord_class.return_value = mock_coordinator
        mock_get_impl.return_value = MagicMock()

        # Mock HA's OAuth2Session
        mock_ha_oauth2_session = MagicMock()
        mock_ha_oauth2_session.async_ensure_token_valid = AsyncMock(
            return_value={
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "expires_in": 3600,
            }
        )
        mock_oauth2_session_class.return_value = mock_ha_oauth2_session

        # Mock aiohttp.ClientSession to prevent unclosed session warning
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()
        mock_client_session.return_value = mock_session

        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        mock_coordinator.async_setup.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_unload_entry."""
    # Mock coordinator in entry.runtime_data
    mock_coordinator = AsyncMock()
    mock_coordinator.api_client.oauth_session.close = AsyncMock()
    mock_config_entry.runtime_data = mock_coordinator

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is True
        mock_unload.assert_called_once()
        mock_coordinator.api_client.oauth_session.close.assert_called_once()
        assert mock_config_entry.runtime_data is None


@pytest.mark.asyncio
async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup."""
    with (
        patch(
            "homeassistant.components.hisense_connectlife.HisenseOAuth2Implementation"
        ) as mock_impl,
        patch(
            "homeassistant.components.hisense_connectlife.OAuth2FlowHandler.async_register_implementation"
        ) as mock_register,
    ):
        mock_impl_instance = MagicMock()
        mock_impl.return_value = mock_impl_instance

        result = await async_setup(hass, {})

        assert result is True
        mock_impl.assert_called_once_with(hass)
        mock_register.assert_called_once()
