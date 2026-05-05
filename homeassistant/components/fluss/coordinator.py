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

from .const import LOGGER, UPDATE_INTERVAL

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
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_get_connectivity(self, device_id: str) -> bool:
        """Return connectivity for a device; False if the status call fails."""
        try:
            status = await self.api.async_get_device_status(device_id)
        except FlussApiClientError:
            return False
        return status["status"]["internetConnected"]

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch Fluss+ devices and merge per-device connectivity status."""
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
        connectivity = await asyncio.gather(
            *(self._async_get_connectivity(d["deviceId"]) for d in device_list)
        )
        return {
            device["deviceId"]: {**device, "internetConnected": connected}
            for device, connected in zip(device_list, connectivity, strict=False)
        }
