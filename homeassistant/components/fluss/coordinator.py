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


class FlussDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        """Fetch device list and per-device connectivity status.

        Credentials are validated by async_get_devices; an auth failure there
        surfaces as ConfigEntryError so the entry enters the reauth flow.

        Devices whose userPermissions.canUseWiFi is false are filtered out
        up front: calling /status on them returns 403 which the library
        classifies as an auth error, but per the Fluss API docs a 403 on a
        per-device status call means "this user lacks WiFi permission for
        this specific device", not "your API key is bad".

        As a safety net for permissions that change between the list and
        status calls, any FlussApiClientError from a per-device status call
        is treated as "that device is unreachable" and the device is marked
        offline rather than failing the whole update.

        Raises:
            ConfigEntryError: authentication failed for the device list.
            UpdateFailed: the device list request failed with a non-auth
                FlussApiClientError.
        """
        try:
            devices = await self.api.async_get_devices()
        except FlussApiClientAuthenticationError as err:
            raise ConfigEntryError(f"Authentication failed: {err}") from err
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching Fluss devices: {err}") from err

        device_list: list[dict[str, Any]] = [
            device
            for device in devices["devices"]
            if device["userPermissions"]["canUseWiFi"]
        ]
        statuses = await asyncio.gather(
            *(self.api.async_get_device_status(d["deviceId"]) for d in device_list),
            return_exceptions=True,
        )

        result: dict[str, dict[str, Any]] = {}
        for device, status in zip(device_list, statuses, strict=True):
            if isinstance(status, FlussApiClientError):
                internet_connected = False
            else:
                internet_connected = bool(status["status"]["internetConnected"])
            result[device["deviceId"]] = {
                **device,
                "internetConnected": internet_connected,
            }
        return result
