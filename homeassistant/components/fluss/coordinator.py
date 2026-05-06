"""DataUpdateCoordinator for Fluss+ integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import COMMAND_REFRESH_DELAY, LOGGER, UPDATE_INTERVAL

type FlussConfigEntry = ConfigEntry[FlussDataUpdateCoordinator]


@dataclass(frozen=True)
class FlussDevice:
    """A Fluss+ device with merged list and status data."""

    device_id: str
    device_name: str | None
    internet_connected: bool
    has_position_sensor: bool
    is_closed: bool | None


class FlussDataUpdateCoordinator(DataUpdateCoordinator[dict[str, FlussDevice]]):
    """Manages fetching Fluss device data on a schedule."""

    config_entry: FlussConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FlussConfigEntry, api_key: str
    ) -> None:
        """Initialize the coordinator."""
        self.api = FlussApiClient(api_key, session=async_get_clientsession(hass))
        # Capability is sticky across refreshes: once a device has reported an
        # openCloseStatus we treat it as cover-capable for the lifetime of the
        # integration so a transient status-fetch failure can't downgrade a
        # cover back to a button.
        self._cover_capable: set[str] = set()
        super().__init__(
            hass,
            LOGGER,
            name=f"Fluss+ ({slugify(api_key[:8])})",
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_get_status(self, device_id: str) -> dict[str, Any] | None:
        """Return per-device status, or ``None`` when the API call fails."""
        try:
            response = await self.api.async_get_device_status(device_id)
        except FlussApiClientError:
            return None
        return response["status"]

    async def _async_update_data(self) -> dict[str, FlussDevice]:
        """Fetch Fluss+ devices and merge per-device status."""
        try:
            devices = await self.api.async_get_devices()
        except FlussApiClientAuthenticationError as err:
            raise ConfigEntryError(f"Authentication failed: {err}") from err
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching Fluss devices: {err}") from err

        device_list = [
            device
            for device in devices["devices"]
            if device["userPermissions"]["canUseWiFi"]
        ]
        statuses = await asyncio.gather(
            *(self._async_get_status(d["deviceId"]) for d in device_list)
        )

        result: dict[str, FlussDevice] = {}
        for device, status in zip(device_list, statuses, strict=True):
            device_id = device["deviceId"]
            previous = self.data.get(device_id) if self.data else None

            if status is None:
                # Per-device fetch failed: preserve last-known state so the
                # cover doesn't flap to unknown on a transient API hiccup.
                internet_connected = False
                is_closed = previous.is_closed if previous else None
            else:
                internet_connected = status.get("internetConnected", False)
                if "openCloseStatus" in status:
                    self._cover_capable.add(device_id)
                    is_closed = status["openCloseStatus"] == "Closed"
                else:
                    is_closed = None

            result[device_id] = FlussDevice(
                device_id=device_id,
                device_name=device.get("deviceName"),
                internet_connected=internet_connected,
                has_position_sensor=device_id in self._cover_capable,
                is_closed=is_closed,
            )
        return result

    @callback
    def async_schedule_device_refresh(self, device_id: str) -> None:
        """Refresh one device's status after the cover has had time to move."""

        async def _refresh(_now: datetime) -> None:
            await self._async_refresh_device(device_id)

        cancel = async_call_later(self.hass, COMMAND_REFRESH_DELAY, _refresh)
        self.config_entry.async_on_unload(cancel)

    async def _async_refresh_device(self, device_id: str) -> None:
        """Refresh status for one device and merge it into coordinator data."""
        if (previous := self.data.get(device_id)) is None:
            return
        status = await self._async_get_status(device_id)
        if status is None:
            return

        has_sensor = previous.has_position_sensor
        if "openCloseStatus" in status:
            self._cover_capable.add(device_id)
            has_sensor = True
            is_closed = status["openCloseStatus"] == "Closed"
        else:
            is_closed = previous.is_closed

        new_data = dict(self.data)
        new_data[device_id] = FlussDevice(
            device_id=device_id,
            device_name=previous.device_name,
            internet_connected=status.get("internetConnected", False),
            has_position_sensor=has_sensor,
            is_closed=is_closed,
        )
        self.async_set_updated_data(new_data)
