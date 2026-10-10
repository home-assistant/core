"""DataUpdateCoordinator for Xthings Cloud."""

from datetime import datetime, timedelta
from typing import Any, override

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
from homeassistant.util import dt as dt_util

from .const import CONF_REFRESH_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type XthingsCloudConfigEntry = ConfigEntry[XthingsCloudCoordinator]

WEBSOCKET_LOCK_STATE_MAX_AGE = timedelta(seconds=DEFAULT_SCAN_INTERVAL)


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
        self._websocket_lock_states: dict[str, tuple[int | bool, datetime]] = {}

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

    @override
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
        data = {device["id"]: device for device in devices}
        now = dt_util.utcnow()
        for device_id, (is_locked, updated_at) in list(
            self._websocket_lock_states.items()
        ):
            if (
                device_id not in data
                or data[device_id]["type"] != "lock"
                or now - updated_at > WEBSOCKET_LOCK_STATE_MAX_AGE
            ):
                self._websocket_lock_states.pop(device_id)
                continue
            data[device_id].setdefault("status", {})["is_locked"] = is_locked
        return data

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
        if (
            "is_locked" in status
            and self.data[device_uuid]["type"] == "lock"
            and isinstance(status["is_locked"], (bool, int))
        ):
            self._websocket_lock_states[device_uuid] = (
                status["is_locked"],
                dt_util.utcnow(),
            )
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
