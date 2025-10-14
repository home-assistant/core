"""Test authentication module for Hisense AC Plugin."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.hisense_connectlife.auth import HisenseAuthProvider
from custom_components.hisense_connectlife.const import DOMAIN


@pytest.mark.asyncio
async def test_get_access_token_application_credentials(mock_hass, mock_config_entry, mock_application_credentials):
    """Test getting access token with Application Credentials."""
    provider = HisenseAuthProvider(mock_hass)
    
    result = await provider.get_access_token(mock_config_entry)
    
    assert result == "test_access_token"


@pytest.mark.asyncio
async def test_get_access_token_legacy_oauth2(mock_hass, mock_legacy_config_entry):
    """Test getting access token with legacy OAuth2."""
    provider = HisenseAuthProvider(mock_hass)
    
    with patch("custom_components.hisense_connectlife.auth.HisenseOAuth2Implementation") as mock_impl:
        mock_session = AsyncMock()
        mock_session.async_ensure_token_valid = AsyncMock()
        mock_session.async_get_access_token = AsyncMock(return_value="test_access_token")
        
        with patch("custom_components.hisense_connectlife.auth.OAuth2Session") as mock_oauth2_session:
            mock_oauth2_session.return_value = mock_session
            
            result = await provider.get_access_token(mock_legacy_config_entry)
            
            assert result == "test_access_token"


@pytest.mark.asyncio
async def test_get_access_token_no_auth_method(mock_hass, mock_config_entry):
    """Test getting access token when no auth method is available."""
    provider = HisenseAuthProvider(mock_hass)
    
    # Remove auth_implementation to simulate no auth method
    mock_config_entry.data = {}
    
    with pytest.raises(ValueError, match="No authentication method available"):
        await provider.get_access_token(mock_config_entry)


@pytest.mark.asyncio
async def test_refresh_token_application_credentials(mock_hass, mock_config_entry, mock_application_credentials):
    """Test refreshing token with Application Credentials."""
    provider = HisenseAuthProvider(mock_hass)
    
    result = await provider.refresh_token(mock_config_entry)
    
    assert "access_token" in result
    assert "refresh_token" in result
    assert "expires_in" in result


@pytest.mark.asyncio
async def test_refresh_token_legacy_oauth2(mock_hass, mock_legacy_config_entry):
    """Test refreshing token with legacy OAuth2."""
    provider = HisenseAuthProvider(mock_hass)
    
    with patch("custom_components.hisense_connectlife.auth.HisenseOAuth2Implementation") as mock_impl:
        mock_impl.return_value.async_refresh_token = AsyncMock(return_value={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        })
        
        with patch.object(mock_hass.config_entries, "async_update_entry") as mock_update:
            result = await provider.refresh_token(mock_legacy_config_entry)
            
            assert result["access_token"] == "new_access_token"
            mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_token_no_token_data(mock_hass, mock_legacy_config_entry):
    """Test refreshing token when no token data is available."""
    provider = HisenseAuthProvider(mock_hass)
    
    # Remove token data
    mock_legacy_config_entry.data = {}
    
    with pytest.raises(ValueError, match="No token data available for refresh"):
        await provider.refresh_token(mock_legacy_config_entry)
