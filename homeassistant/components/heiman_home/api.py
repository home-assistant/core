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
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

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

        # 初始化 HTTP 客户端和云客户端
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
            api_url="https://spapi.heiman.cn", access_token=access_token
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

    def get_access_token(self) -> str | None:
        """Get current access token."""
        return self._get_access_token()

    @property
    def cloud_client(self) -> HeimanCloudClient | None:
        """Return the cloud client."""
        return self._cloud_client

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        if self._session:
            try:
                await self._session.async_ensure_token_valid()
            except (OAuth2TokenRequestError, OAuth2TokenRequestReauthError) as err:
                _LOGGER.error("Token refresh failed: %s", err)
                raise ConfigEntryAuthFailed(f"Token refresh failed: {err}") from err

        # 如果 token 已更新，重新初始化客户端
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
            raise HeimanConnectionError(message="Client not initialized")

        try:
            user = await self._cloud_client.async_get_user_info()
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError:
            raise
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
            raise HeimanConnectionError(message="Client not initialized")

        try:
            homes = await self._cloud_client.async_get_homes()
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError:
            raise
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
            raise HeimanConnectionError(message="Client not initialized")

        try:
            self._cloud_client.home_id = home_id
            devices = await self._cloud_client.async_get_devices(home_id=home_id)
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError:
            raise
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
            raise HeimanConnectionError(message="Client not initialized")

        try:
            properties = await self._cloud_client.async_get_device_properties(device_id)
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError:
            raise
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error getting device properties for %s",
                device_id,
            )
            raise HeimanConnectionError(
                f"Failed to get device properties: {err}"
            ) from err
        else:
            _LOGGER.debug(
                "Retrieved properties for device %s: %s", device_id, properties
            )
            return properties

    async def async_get_device_detail(self, device_id: str) -> dict[str, Any] | None:
        """Get device detail info if supported by the client."""
        await self._ensure_authenticated()

        cloud_client = self._cloud_client
        if not cloud_client:
            raise HeimanConnectionError(message="Client not initialized")

        detail_method = getattr(cloud_client, "async_get_device_detail", None)
        if not callable(detail_method):
            return None

        try:
            return await detail_method(device_id)
        except TypeError:
            return await detail_method(device_id=device_id)

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
            raise HeimanConnectionError(message="Client not initialized")

        try:
            result = await self._cloud_client.async_control_device(
                device_id=device_id,
                property_identifier=property_identifier,
                value=value,
            )
        except HeimanAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except HeimanConnectionError:
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error controlling device: %s", err)
            raise HeimanConnectionError(f"Failed to control device: {err}") from err
        else:
            _LOGGER.debug(
                "Successfully controlled device %s: %s=%s",
                device_id,
                property_identifier,
                value,
            )
            return result

    async def close(self) -> None:
        """Close the client."""
        if self._http_client:
            await self._http_client.close()
