"""DataUpdateCoordinator for Fluss+ integration."""

from __future__ import annotations

from datetime import timedelta
import logging
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

_LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = 60  # seconds


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
        except Exception as e:
            raise ConfigEntryNotReady(
                f"Failed to initialize Fluss API client: {e}"
            ) from e
        super().__init__(
            hass,
            _LOGGER,
            name=f"Fluss+ ({slugify(api_key[:8])})",
            config_entry=config_entry,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the Fluss API and return as a dictionary keyed by deviceId."""
        try:
            devices = await self.api.async_get_devices()
            return {
                device["deviceId"]: device
                for device in devices.get("devices", [])
                if isinstance(device, dict) and "deviceId" in device
            }
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching Fluss devices: {err}") from err
