"""DataUpdateCoordinator for Xthings Cloud."""

from __future__ import annotations

import base64
from datetime import timedelta
import json
import time
from typing import Any

from ha_xthings_cloud import (
    XthingsCloudApiClient,
    XthingsCloudApiError,
    XthingsCloudAuthError,
    XthingsCloudWebSocket,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_TOKEN, CONF_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type XthingsCloudConfigEntry = ConfigEntry[XthingsCloudCoordinator]


def _is_token_expired(token: str) -> bool:
    """Check if a JWT token is expired or about to expire (within 60s)."""
    try:
        payload = token.split(".")[1]
        # Add padding for base64 decoding
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data.get("exp", 0) < time.time() + 60
    except (IndexError, ValueError):
        return True


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
        self.devices: list[dict[str, Any]] = []
        self.websocket: XthingsCloudWebSocket | None = None

    async def _async_refresh_token(self) -> bool:
        """Try to refresh token using refresh_token."""
        refresh_token = self.config_entry.data.get(CONF_REFRESH_TOKEN)
        if not refresh_token:
            return False
        try:
            token_data = await self.client.async_refresh_token(refresh_token)
        except XthingsCloudAuthError:
            return False
        else:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_TOKEN: token_data["token"],
                    CONF_REFRESH_TOKEN: token_data["refresh_token"],
                },
            )
            return True

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest device data from cloud."""
        if _is_token_expired(self.config_entry.data[CONF_TOKEN]):
            if not await self._async_refresh_token():
                raise ConfigEntryAuthFailed(
                    "Token expired and refresh failed, re-authentication required"
                )
        try:
            self.devices = await self.client.async_get_devices()
            return {device["id"]: device for device in self.devices}
        except XthingsCloudAuthError:
            if await self._async_refresh_token():
                try:
                    self.devices = await self.client.async_get_devices()
                    return {device["id"]: device for device in self.devices}
                except XthingsCloudAuthError as err:
                    raise ConfigEntryAuthFailed(
                        "Token refresh failed, re-authentication required"
                    ) from err
            raise ConfigEntryAuthFailed(
                "Invalid token, re-authentication required"
            ) from None
        except XthingsCloudApiError as err:
            raise UpdateFailed(f"Failed to fetch data: {err}") from err

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
        if not self.data:
            return
        for device_data in self.data.values():
            if device_data.get("id") == device_uuid:
                if "online" in status:
                    device_data["online"] = status.pop("online")
                if status:
                    device_data.setdefault("status", {}).update(status)
                LOGGER.debug("WebSocket updated device status: %s", device_uuid)
                self.async_set_updated_data(self.data)
                return
        LOGGER.debug("WebSocket received status for unknown device: %s", device_uuid)

    async def _handle_ws_token_expired(self) -> None:
        """Handle WebSocket auth expiry, refresh token."""
        if await self._async_refresh_token():
            new_token = self.config_entry.data[CONF_TOKEN]
            self.client.token = new_token
            if self.websocket:
                self.websocket.token = new_token
            LOGGER.info("WebSocket token refreshed successfully")
        else:
            LOGGER.error("WebSocket token refresh failed")
