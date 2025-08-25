"""DataUpdateCoordinator for Fluss+ integration."""

from __future__ import annotations

from typing import Any

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import LOGGER, UPDATE_INTERVAL_TIMEDELTA


class FlussDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages fetching Fluss device data on a schedule."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api_key: str
    ) -> None:
        """Initialize the coordinator."""
        try:
            self.api = FlussApiClient(api_key)
        except FlussApiClientAuthenticationError as e:
            raise ConfigEntryAuthFailed from e
        except (FlussApiClientCommunicationError, FlussApiClientError) as e:
            raise ConfigEntryNotReady from e
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
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching Fluss devices: {err}") from err

        return {
            device["deviceId"]: device
            for device in devices.get("devices", [])
            if isinstance(device, dict) and "deviceId" in device
        }
