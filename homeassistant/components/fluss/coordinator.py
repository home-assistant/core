"""DataUpdateCoordinator for Fluss+ integration."""

from __future__ import annotations

import asyncio
from typing import Any

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import LOGGER, UPDATE_INTERVAL_TIMEDELTA

type FlussConfigEntry = ConfigEntry[FlussDataUpdateCoordinator]


class FlussDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Manages fetching Fluss device data on a schedule."""

    def __init__(
        self, hass: HomeAssistant, config_entry: FlussConfigEntry, api_key: str
    ) -> None:
        """Initialize the coordinator."""
        self.api = FlussApiClient(api_key, session=async_get_clientsession(hass))
        super().__init__(
            hass,
            LOGGER,
            name=f"Fluss+ ({slugify(api_key[:8])})",
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL_TIMEDELTA,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Return devices keyed by deviceId with internetConnected merged in.

        Only devices where the user has canUseWiFi permission are included;
        per-device status errors mark that device offline.

        Raises:
            ConfigEntryError: credentials rejected by async_get_devices.
            UpdateFailed: device list fetch failed for another reason.
        """
        try:
            devices = await self.api.async_get_devices()
        except FlussApiClientAuthenticationError as err:
            raise ConfigEntryError(f"Authentication failed: {err}") from err
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching Fluss devices: {err}") from err

        if not isinstance(devices, dict):
            raise UpdateFailed("Error fetching Fluss devices: invalid response data")

        raw_device_list = devices.get("devices")
        if not isinstance(raw_device_list, list):
            raise UpdateFailed("Error fetching Fluss devices: invalid devices data")

        device_list: list[dict[str, Any]] = [
            device
            for device in raw_device_list
            if isinstance(device, dict)
            and isinstance(device.get("userPermissions"), dict)
            and bool(device["userPermissions"].get("canUseWiFi"))
            and isinstance(device.get("deviceId"), str)
            and bool(device["deviceId"])
        ]
        statuses = await asyncio.gather(
            *(self.api.async_get_device_status(d["deviceId"]) for d in device_list),
            return_exceptions=True,
        )

        result: dict[str, dict[str, Any]] = {}
        for device, status in zip(device_list, statuses, strict=True):
            if isinstance(status, FlussApiClientError):
                result[device["deviceId"]] = {**device, "internetConnected": False}
                continue
            if isinstance(status, BaseException):
                raise status

            internet_connected = False
            if isinstance(status, dict):
                status_data = status.get("status")
                if isinstance(status_data, dict):
                    internet_connected = bool(status_data.get("internetConnected"))

            result[device["deviceId"]] = {
                **device,
                "internetConnected": internet_connected,
            }
        return result
