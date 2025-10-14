"""Test the Hisense ConnectLife integration initialization."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .common import mock_config_entry, mock_coordinator


@pytest.mark.asyncio
async def test_async_setup_entry(hass: HomeAssistant, mock_config_entry: ConfigEntry):
    """Test async_setup_entry."""
    from custom_components.hisense_connectlife import async_setup_entry
    
    with patch("custom_components.hisense_connectlife.HisenseACPluginDataUpdateCoordinator") as mock_coord_class:
        mock_coordinator = AsyncMock()
        mock_coordinator.async_setup = AsyncMock(return_value=True)
        mock_coord_class.return_value = mock_coordinator
        
        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is True
        mock_coordinator.async_setup.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant, mock_config_entry: ConfigEntry):
    """Test async_unload_entry."""
    from custom_components.hisense_connectlife import async_unload_entry
    
    # Mock coordinator in hass.data
    mock_coordinator = AsyncMock()
    mock_coordinator.api_client.oauth_session.close = AsyncMock()
    hass.data = {
        "hisense_connectlife": {
            mock_config_entry.entry_id: mock_coordinator
        }
    }
    
    with patch("homeassistant.config_entries.async_unload_platforms", return_value=True) as mock_unload:
        result = await async_unload_entry(hass, mock_config_entry)
        
        assert result is True
        mock_unload.assert_called_once()
        mock_coordinator.api_client.oauth_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup(hass: HomeAssistant):
    """Test async_setup."""
    from custom_components.hisense_connectlife import async_setup
    
    with patch("custom_components.hisense_connectlife.HisenseOAuth2Implementation") as mock_impl, \
         patch("custom_components.hisense_connectlife.HisenseApplicationCredentials") as mock_app_creds, \
         patch("custom_components.hisense_connectlife.OAuth2FlowHandler.async_register_implementation") as mock_register:
        
        mock_app_creds_instance = AsyncMock()
        mock_app_creds.return_value = mock_app_creds_instance
        
        result = await async_setup(hass, {})
        
        assert result is True
        mock_register.assert_called_once()
        mock_app_creds_instance.async_get_auth_implementation.assert_called_once()
