"""API wrapper for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import (
    HeimanAuthError,
    HeimanCloudClient,
    HeimanConnectionError,
    HeimanDevice,
    HeimanHome,
    HeimanHttpClient,
    HeimanUser,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class HeimanApiClient:
    """Heiman API client for Home Assistant."""

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

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        if self._session:
            try:
                await self._session.async_ensure_token_valid()
            except Exception as err:
                _LOGGER.error("Token refresh failed: %s", err)
                raise ConfigEntryAuthFailed(f"Token refresh failed: {err}") from err

        # Re-initialize client if token updated
        current_token = self._get_access_token()
        if self._http_client and current_token:
            self._http_client.update_access_token(current_token)

    async def async_get_user_info(self) -> HeimanUser:
        """Get current user information.

        Returns:
            HeimanUser object with user details

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            HeimanConnectionError: If network request fails
        """
        await self._ensure_authenticated()

        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")

        try:
            user = await self._cloud_client.async_get_user_info()
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error getting user info: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error getting user info")
            raise HeimanConnectionError(f"Failed to get user info: {err}") from err
        else:
            _LOGGER.debug("Retrieved user info: %s", user.email)
            return user

    async def async_get_homes(self) -> list[HeimanHome]:
        """Get list of homes for current user.

        Returns:
            List of HeimanHome objects

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            HeimanConnectionError: If network request fails
        """
        await self._ensure_authenticated()

        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")

        try:
            homes = await self._cloud_client.async_get_homes()
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error getting homes: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error getting homes")
            raise HeimanConnectionError(f"Failed to get homes: {err}") from err
        else:
            _LOGGER.debug("Retrieved %d homes", len(homes))
            return homes

    async def async_get_devices(self, home_id: str) -> dict[str, HeimanDevice]:
        """Get list of devices in specified home.

        Args:
            home_id: Home ID to fetch devices from

        Returns:
            Dictionary mapping device_id to HeimanDevice objects

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            HeimanConnectionError: If network request fails
        """
        await self._ensure_authenticated()

        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")

        try:
            # Set current home ID
            self._cloud_client.home_id = home_id
            devices = await self._cloud_client.async_get_devices(home_id=home_id)
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error getting devices: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error getting devices")
            raise HeimanConnectionError(f"Failed to get devices: {err}") from err
        else:
            _LOGGER.debug("Retrieved %d devices", len(devices))
            return devices

    async def async_get_device_properties(self, device_id: str) -> dict[str, Any]:
        """Get current properties of a device.

        Args:
            device_id: Device ID

        Returns:
            Dictionary of property identifier to value

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            HeimanConnectionError: If network request fails
        """
        await self._ensure_authenticated()

        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")

        try:
            properties = await self._cloud_client.async_get_device_properties(device_id)
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(
                f"Connection error getting device properties: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error getting device properties")
            raise HeimanConnectionError(
                f"Failed to get device properties: {err}"
            ) from err
        else:
            _LOGGER.debug(
                "Retrieved properties for device %s: %s", device_id, properties
            )
            return properties

    async def async_control_device(
        self,
        device_id: str,
        property_identifier: str,
        value: Any,
    ) -> bool:
        """Control device by setting property value.

        Args:
            device_id: Target device ID
            property_identifier: Property to control
            value: Value to set

        Returns:
            True if control successful

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            HeimanConnectionError: If network request fails
        """
        await self._ensure_authenticated()

        if not self._cloud_client:
            raise HeimanConnectionError("Client not initialized")

        try:
            result = await self._cloud_client.async_control_device(
                device_id=device_id,
                property_identifier=property_identifier,
                value=value,
            )
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError as err:
            raise UpdateFailed(f"Connection error controlling device: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error controlling device")
            raise HeimanConnectionError(f"Failed to control device: {err}") from err
        else:
            _LOGGER.debug(
                "Successfully controlled device %s: %s=%s",
                device_id,
                property_identifier,
                value,
            )
            return result

    async def async_get_device_detail(self, device_id: str) -> dict[str, Any] | None:
        """Get detailed device information.

        Args:
            device_id: Device ID

        Returns:
            Dictionary with device details or None if not available

        Note:
            This method uses the internal _async_get_device_detail from heimanconnect
            library as there is no public API available. This is necessary to access
            deriveMetadata which contains real-time property values.
        """
        if not self._cloud_client:
            _LOGGER.warning("Cloud client not initialized")
            return None

        try:
            # Use the internal method to get device detail
            # Note: This accesses a private method from heimanconnect library
            # because deriveMetadata (containing property values) is only available
            # through this internal endpoint
            return await self._cloud_client._async_get_device_detail(device_id)  # noqa: SLF001
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to get device detail for %s: %s", device_id, err)
            return None

    async def close(self) -> None:
        """Close the client."""
        if self._http_client:
            await self._http_client.close()
