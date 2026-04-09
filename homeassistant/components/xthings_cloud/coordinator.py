"""DataUpdateCoordinator for Xthings Cloud."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import XthingsCloudApiClient, XthingsCloudApiError, XthingsCloudAuthError
from .const import CONF_REFRESH_TOKEN, CONF_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER
from .websocket import XthingsCloudWebSocket


class XthingsCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Xthings Cloud data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: XthingsCloudApiClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass, LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.entry = entry
        self.devices: list[dict[str, Any]] = []
        self.websocket: XthingsCloudWebSocket | None = None

    async def _async_refresh_token(self) -> bool:
        """Try to refresh token using refresh_token."""
        refresh_token = self.entry.data.get(CONF_REFRESH_TOKEN)
        if not refresh_token:
            return False
        try:
            token_data = await self.client.async_refresh_token(refresh_token)
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data,
                      CONF_TOKEN: token_data["token"],
                      CONF_REFRESH_TOKEN: token_data.get("refresh_token", "")},
            )
            return True
        except XthingsCloudAuthError:
            return False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest device data from cloud."""
        try:
            self.devices = await self.client.async_get_devices()
            self._normalize_device_status(self.devices)
            return {device["id"]: device for device in self.devices}
        except XthingsCloudAuthError:
            if await self._async_refresh_token():
                try:
                    self.devices = await self.client.async_get_devices()
                    self._normalize_device_status(self.devices)
                    return {device["id"]: device for device in self.devices}
                except XthingsCloudAuthError as err:
                    raise ConfigEntryAuthFailed(
                        "Token refresh failed, re-authentication required"
                    ) from err
            raise ConfigEntryAuthFailed(
                "Invalid token, re-authentication required"
            )
        except XthingsCloudApiError as err:
            raise UpdateFailed(f"Failed to fetch data: {err}") from err

    @staticmethod
    def _normalize_device_status(devices: list[dict[str, Any]]) -> None:
        """Normalize device status fields (battery_percent -> battery)."""
        for device in devices:
            status = device.get("status", {})
            if "battery_percent" in status:
                status["battery"] = status["battery_percent"]

    async def async_start_websocket(self) -> None:
        """Start WebSocket connection."""
        if self.websocket:
            return
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        session = async_get_clientsession(self.hass)
        token = self.entry.data.get(CONF_TOKEN, "")
        self.websocket = XthingsCloudWebSocket(
            session=session, token=token,
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
        if not self.data:
            return
        for device_id, device_data in self.data.items():
            if device_data.get("id") == device_uuid:
                # Update online field at device top level
                if "online" in status:
                    device_data["online"] = status.pop("online")
                # Update remaining fields in status sub-object
                if status:
                    device_data.setdefault("status", {}).update(status)
                LOGGER.debug("WebSocket updated device status: %s", device_uuid)
                self.async_set_updated_data(self.data)
                return
        LOGGER.debug("WebSocket received status for unknown device: %s", device_uuid)

    async def _handle_ws_token_expired(self) -> None:
        """Handle WebSocket auth expiry, refresh token."""
        if await self._async_refresh_token():
            new_token = self.entry.data.get(CONF_TOKEN, "")
            self.client._token = new_token
            if self.websocket:
                self.websocket.token = new_token
            LOGGER.info("WebSocket token refreshed successfully")
        else:
            LOGGER.error("WebSocket token refresh failed")
