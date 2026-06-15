"""DataUpdateCoordinator for Xthings Cloud."""

from datetime import timedelta
from typing import Any

from ha_xthings_cloud import (
    XthingsCloudApiClient,
    XthingsCloudApiError,
    XthingsCloudAuthError,
    XthingsCloudWebSocket,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type XthingsCloudConfigEntry = ConfigEntry[XthingsCloudCoordinator]


class XthingsCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Xthings Cloud data update coordinator."""

    config_entry: XthingsCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: XthingsCloudApiClient,
        entry: XthingsCloudConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self.websocket: XthingsCloudWebSocket | None = None

    async def _async_ensure_token_valid(self) -> None:
        """Ensure the token is valid, refresh if expired.

        Raises ConfigEntryAuthFailed if refresh fails.
        """
        if not self.client.is_token_expired():
            return
        try:
            token_data = await self.client.async_refresh_token(
                self.config_entry.data[CONF_REFRESH_TOKEN]
            )
        except XthingsCloudAuthError as err:
            raise ConfigEntryAuthFailed(
                "Token expired and refresh failed, re-authentication required"
            ) from err
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_TOKEN: token_data["token"],
                CONF_REFRESH_TOKEN: token_data["refresh_token"],
            },
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest device data from cloud."""
        await self._async_ensure_token_valid()
        try:
            devices = await self.client.async_get_devices()
        except XthingsCloudAuthError as err:
            raise ConfigEntryAuthFailed(
                "Invalid token, re-authentication required"
            ) from err
        except XthingsCloudApiError as err:
            raise UpdateFailed(f"Failed to fetch data: {err}") from err
        return {device["id"]: device for device in devices}

    async def async_start_websocket(self) -> None:
        """Start WebSocket connection."""
        if self.websocket:
            return
        session = async_get_clientsession(self.hass)
        token = self.config_entry.data[CONF_TOKEN]
        self.websocket = XthingsCloudWebSocket(
            session=session,
            token=token,
            on_device_status=self._handle_ws_device_status,
            on_token_expired=self._handle_ws_token_expired,
        )
        await self.websocket.async_start()

    async def async_stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self.websocket:
            await self.websocket.async_stop()
            self.websocket = None

    def _handle_ws_device_status(
        self, device_uuid: str, status: dict[str, Any]
    ) -> None:
        """Handle WebSocket device status update."""
        if not self.data or device_uuid not in self.data:
            LOGGER.debug(
                "WebSocket received status for unknown device: %s", device_uuid
            )
            return
        device_data = self.data[device_uuid]
        device_data.setdefault("status", {}).update(status)
        LOGGER.debug("WebSocket updated device status: %s", device_uuid)
        self.async_set_updated_data(self.data)

    async def _handle_ws_token_expired(self) -> None:
        """Handle WebSocket auth expiry, refresh token."""
        try:
            await self._async_ensure_token_valid()
        except ConfigEntryAuthFailed:
            LOGGER.error("WebSocket token refresh failed")
            return
        new_token = self.config_entry.data[CONF_TOKEN]
        self.client.token = new_token
        if self.websocket:
            self.websocket.token = new_token
        LOGGER.info("WebSocket token refreshed successfully")
