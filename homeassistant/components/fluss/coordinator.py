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
        """Fetch data from the Fluss API and return as a dictionary keyed by deviceId."""
        try:
            devices = await self.api.async_get_devices()
        except FlussApiClientAuthenticationError as err:
            raise ConfigEntryError(f"Authentication failed: {err}") from err
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching Fluss devices: {err}") from err

        device_list = devices.get("devices", [])
        statuses = await asyncio.gather(
            *(
                self._async_get_device_status(device["deviceId"])
                for device in device_list
            )
        )

        return {
            device["deviceId"]: {**device, "status": status}
            for device, status in zip(device_list, statuses, strict=True)
        }

    async def _async_get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Fetch status for a single device, returning None on failure."""
        try:
            return await self.api.async_get_device_status(device_id)
        except FlussApiClientError as err:
            LOGGER.debug("Failed to get status for device %s: %s", device_id, err)
            return None
