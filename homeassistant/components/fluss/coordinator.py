"""DataUpdateCoordinator for Fluss+ integration."""

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
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import COMMAND_REFRESH_COOLDOWN, LOGGER, UPDATE_INTERVAL

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
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=COMMAND_REFRESH_COOLDOWN,
                immediate=False,
            ),
        )

    async def _async_get_status(self, device_id: str) -> dict[str, Any]:
        """Return per-device status."""
        try:
            response = await self.api.async_get_device_status(device_id)
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching status for {device_id}: {err}") from err
        return response["status"]

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
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
        return {
            device["deviceId"]: {**device, **status}
            for device, status in zip(device_list, statuses, strict=False)
        }
