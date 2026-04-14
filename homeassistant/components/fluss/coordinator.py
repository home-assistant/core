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

        device_list: list[dict[str, Any]] = devices.get("devices", [])
        statuses = await asyncio.gather(
            *(self.api.async_get_device_status(d["deviceId"]) for d in device_list),
            return_exceptions=True,
        )

        result: dict[str, dict[str, Any]] = {}
        for device, status in zip(device_list, statuses, strict=True):
            merged = dict(device)
            if isinstance(status, BaseException):
                merged["internetConnected"] = False
            else:
                merged["internetConnected"] = bool(
                    status.get("status", {}).get("internetConnected")
                )
            result[device["deviceId"]] = merged
        return result
