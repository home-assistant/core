"""API wrapper for Heiman integration.

This module provides a thin wrapper around the heimanconnect library,
handling OAuth2 token management and client initialization.
"""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import (
    HeimanAuthError,
    HeimanCloudClient,
    HeimanConnectionError,
    HeimanHttpClient,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class HeimanApiClient:
    """Heiman API client for Home Assistant.

    This is a thin wrapper that manages OAuth2 token lifecycle
    and provides access to the underlying HeimanCloudClient.
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

        # Initialize HTTP and cloud clients
        self._http_client: HeimanHttpClient | None = None
        self._cloud_client: HeimanCloudClient | None = None

        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize HTTP and cloud clients."""
        access_token = self._get_access_token()

        if not access_token:
            _LOGGER.warning("No access token available")
            return

        self._http_client = HeimanHttpClient(
            api_url=API_BASE_URL, access_token=access_token
        )

        self._cloud_client = HeimanCloudClient(
            http_client=self._http_client,
        )

    def _get_access_token(self) -> str | None:
        """Get current access token."""
        if self._session and self._session.token:
            return self._session.token.get("access_token")
        if self._token_data:
            return self._token_data.get("access_token")
        return None

    async def async_ensure_token_valid(self) -> None:
        """Ensure OAuth2 token is valid.

        Raises:
            ConfigEntryAuthFailed: If token refresh fails due to auth error
            UpdateFailed: If token refresh fails due to transient error
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
            # Update token in HTTP client if it changed
            current_token = self._get_access_token()
            if self._http_client and current_token:
                self._http_client.update_access_token(current_token)

    @property
    def cloud_client(self) -> HeimanCloudClient:
        """Get the underlying cloud client.

        Returns:
            HeimanCloudClient instance

        Raises:
            RuntimeError: If client is not initialized
        """
        if not self._cloud_client:
            raise RuntimeError("Cloud client not initialized")
        return self._cloud_client

    async def close(self) -> None:
        """Close the client."""
        if self._http_client:
            await self._http_client.close()

    # Proxy methods to cloud_client for backward compatibility

    async def async_get_user_info(self):
        """Get user info from cloud client."""
        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")
        await self.async_ensure_token_valid()
        try:
            return await self._cloud_client.async_get_user_info()
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise Exception(f"Failed to get user info: {err}") from err

    async def async_get_homes(self):
        """Get homes from cloud client."""
        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")
        await self.async_ensure_token_valid()
        try:
            return await self._cloud_client.async_get_homes()
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error getting homes: {err}") from err
        except Exception as err:
            raise HeimanConnectionError(f"Failed to get homes: {err}") from err

    async def async_get_devices(self, home_id: str):
        """Get devices from cloud client."""
        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")
        await self.async_ensure_token_valid()
        try:
            return await self._cloud_client.async_get_devices(home_id=home_id)
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error getting devices: {err}") from err
        except Exception as err:
            raise HeimanConnectionError(f"Failed to get devices: {err}") from err

    async def async_get_device_properties(self, device_id: str):
        """Get device properties from cloud client."""
        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")
        await self.async_ensure_token_valid()
        try:
            return await self._cloud_client.async_get_device_properties(device_id)
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error getting device properties: {err}") from err
        except Exception as err:
            raise Exception(f"Failed to get device properties: {err}") from err

    async def async_get_device_detail(self, device_id: str):
        """Get device detail from cloud client."""
        if not self._cloud_client:
            return None
        await self.async_ensure_token_valid()
        try:
            return await self._cloud_client._async_get_device_detail(device_id)
        except Exception:  # noqa: BLE001
            return None

    async def async_control_device(self, device_id: str, property_id: str, value):
        """Control device via cloud client."""
        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")
        await self.async_ensure_token_valid()
        try:
            return await self._cloud_client.async_control_device(device_id, property_id, value)
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error controlling device: {err}") from err
        except Exception as err:
            raise HeimanConnectionError(f"Failed to control device: {err}") from err
