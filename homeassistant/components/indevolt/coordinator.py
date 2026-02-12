"""Home Assistant integration for Indevolt device."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from indevolt_api import IndevoltAPI, TimeOutException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = 30

type IndevoltConfigEntry = ConfigEntry[IndevoltCoordinator]


class IndevoltCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching and pushing data to indevolt devices."""

    config_entry: IndevoltConfigEntry

    def __init__(self, hass: HomeAssistant, entry: IndevoltConfigEntry) -> None:
        """Initialize the indevolt coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            config_entry=entry,
        )

        # Initialize Indevolt API
        self.api = IndevoltAPI(
            host=entry.data[CONF_HOST],
            port=DEFAULT_PORT,
            session=async_get_clientsession(hass),
        )

        self.serial_number: str
        self.device_model: str | None
        self.firmware_version: str | None
        self.generation: int
        self._initial_sensor_keys: list[str] = []

    async def async_initialize(self) -> None:
        """Fetch device info once on boot."""
        try:
            config_data = await self.api.get_config()
        except TimeOutException as err:
            raise ConfigEntryNotReady(
                f"Device config retrieval timed out: {err}"
            ) from err

        # Cache device information
        device_data = config_data.get("device", {})

        self.serial_number = device_data.get("sn")
        self.device_model = device_data.get("type")
        self.firmware_version = device_data.get("fw")
        self.generation = device_data.get("generation", 1)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch raw JSON data from the device."""
        sensor_keys = list(self.async_contexts())
        if not sensor_keys:
            return {}

        try:
            return await self.api.fetch_data(sensor_keys)
        except TimeOutException as err:
            raise UpdateFailed(f"Device update timed out: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Device update failed: {err}") from err

    async def async_fetch_sensors(self, sensor_keys: list[str]) -> dict[str, Any]:
        """Fetch specific sensors from the device by keys."""
        if not sensor_keys:
            return {}

        try:
            return await self.api.fetch_data(sensor_keys)
        except TimeOutException as err:
            raise HomeAssistantError(
                f"Device timed out fetching sensors: {err}"
            ) from err
        except Exception as err:
            raise HomeAssistantError(f"Failed to fetch sensors: {err}") from err
