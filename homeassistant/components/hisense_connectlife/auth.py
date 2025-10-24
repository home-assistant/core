"""Authentication module for Hisense AC Plugin with Application Credentials support."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import CLIENT_ID, CLIENT_SECRET, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)


class HisenseOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Hisense OAuth2 implementation for Application Credentials."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Hisense OAuth2 implementation."""
        super().__init__(
            hass=hass,
            domain="hisense_connectlife",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Hisense Air Conditioner"

    @property
    def redirect_uri(self) -> str:
        """Return the redirect URI."""
        return "http://homeassistant.local:8123/auth/external/callback"


class HisenseAuthProvider:
    """Authentication provider that supports both Application Credentials and legacy OAuth2."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the auth provider."""
        self.hass = hass

    async def get_access_token(self, config_entry) -> str:
        """Get access token from either Application Credentials or legacy OAuth2."""
        # Check if using Application Credentials
        if "auth_implementation" in config_entry.data:
            _LOGGER.debug("Using Application Credentials for authentication")
            return await self._get_app_credentials_token(config_entry)
        else:
            _LOGGER.debug("Using legacy OAuth2 for authentication")
            return await self._get_legacy_oauth2_token(config_entry)

    async def _get_app_credentials_token(self, config_entry) -> str:
        """Get token from Application Credentials."""
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            self.hass, config_entry
        )
        
        session = OAuth2Session(self.hass, config_entry, implementation)
        token_info = await session.async_ensure_token_valid()
        
        if not token_info:
            raise ValueError("No valid token available from Application Credentials")
            
        return token_info["access_token"]

    async def _get_legacy_oauth2_token(self, config_entry) -> str:
        """Get token from legacy OAuth2 implementation."""
        from .oauth2 import HisenseOAuth2Implementation, OAuth2Session
        
        implementation = HisenseOAuth2Implementation(self.hass)
        token_info = config_entry.data.get("token", {})
        
        if not token_info:
            raise ValueError("No token data available in config entry")
            
        oauth_session = OAuth2Session(
            hass=self.hass,
            oauth2_implementation=implementation,
            token=token_info,
        )
        
        await oauth_session.async_ensure_token_valid()
        return await oauth_session.async_get_access_token()

    async def refresh_token(self, config_entry) -> dict[str, Any]:
        """Refresh token for both authentication methods."""
        if "auth_implementation" in config_entry.data:
            return await self._refresh_app_credentials_token(config_entry)
        else:
            return await self._refresh_legacy_oauth2_token(config_entry)

    async def _refresh_app_credentials_token(self, config_entry) -> dict[str, Any]:
        """Refresh token using Application Credentials."""
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            self.hass, config_entry
        )
        
        session = OAuth2Session(self.hass, config_entry, implementation)
        token_info = await session.async_ensure_token_valid()
        
        if not token_info:
            raise ValueError("Failed to refresh token using Application Credentials")
            
        return token_info

    async def _refresh_legacy_oauth2_token(self, config_entry) -> dict[str, Any]:
        """Refresh token using legacy OAuth2."""
        from .oauth2 import HisenseOAuth2Implementation
        
        implementation = HisenseOAuth2Implementation(self.hass)
        token_info = config_entry.data.get("token", {})
        
        if not token_info:
            raise ValueError("No token data available for refresh")
            
        new_token = await implementation.async_refresh_token(token_info)
        
        # Update config entry with new token
        self.hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, "token": new_token}
        )
        
        return new_token
