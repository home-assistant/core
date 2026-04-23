"""API wrapper for Heiman integration.

This module provides a thin wrapper around the heimanconnect library,
handling OAuth2 token management and client initialization.
"""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import (
    HeimanAuthError,
    HeimanCloudClientWrapper,
    HeimanConnectionError,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import API_BASE_URL


_LOGGER = logging.getLogger(__name__)


class HeimanApiClient:
    """Heiman API client for Home Assistant.

    This is a thin wrapper that manages OAuth2 token lifecycle
    and delegates to HeimanCloudClientWrapper for API operations.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        session: OAuth2Session | None = None,
        token_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            hass: Home Assistant instance
            session: OAuth2 session for token management
            token_data: Token data for temporary use (e.g., during config flow)
        """
        self.hass = hass
        self._session = session
        self._token_data = token_data
        self._wrapper: HeimanCloudClientWrapper | None = None

    async def _get_access_token(self) -> str | None:
        """Get current access token."""
        if self._session and self._session.token:
            return self._session.token.get("access_token")
        if self._token_data:
            return self._token_data.get("access_token")
        return None

    async def _ensure_initialized(self) -> None:
        """Ensure the wrapper is initialized with a valid token."""
        if self._wrapper:
            return

        access_token = await self._get_access_token()
        if not access_token:
            raise HeimanConnectionError("No access token available")

        # Create wrapper with token refresh callback
        self._wrapper = HeimanCloudClientWrapper(
            api_url=API_BASE_URL,
            initial_access_token=access_token,
            token_refresh_callback=self._refresh_token_callback,
        )

    async def _refresh_token_callback(self) -> str:
        """Callback to refresh the access token.

        Returns:
            New access token string

        Raises:
            Exception: If token refresh fails
        """
        if self._session:
            try:
                await self._session.async_ensure_token_valid()
            except OAuth2TokenRequestTransientError as err:
                raise UpdateFailed(f"Temporary token refresh error: {err}") from err
            except OAuth2TokenRequestReauthError as err:
                raise ConfigEntryAuthFailed(f"Token expired: {err}") from err
            except Exception as err:
                raise UpdateFailed(f"Token refresh failed: {err}") from err

            # Get updated token
            new_token = self._session.token.get("access_token")
            if new_token:
                return new_token

        # Fallback to token_data
        if self._token_data:
            return self._token_data.get("access_token", "")

        raise HeimanAuthError("No token available for refresh")

    @property
    def cloud_client(self):
        """Get the underlying cloud client wrapper.

        Returns:
            HeimanCloudClientWrapper instance

        Raises:
            RuntimeError: If client is not initialized
        """
        if not self._wrapper:
            raise RuntimeError("Client not initialized")
        return self._wrapper

    async def close(self) -> None:
        """Close the client and release resources."""
        if self._wrapper:
            await self._wrapper.close()
            self._wrapper = None
