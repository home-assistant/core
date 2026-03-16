"""Home Assistant integration for Indevolt device."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError
from indevolt_api import IndevoltAPI, TimeOutException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_GENERATION,
    CONF_SERIAL_NUMBER,
    DEFAULT_PORT,
    DOMAIN,
    SENSOR_KEYS,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = 30

type IndevoltConfigEntry = ConfigEntry[IndevoltCoordinator]


class IndevoltCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching and pushing data to indevolt devices."""

    config_entry: IndevoltConfigEntry
    firmware_version: str | None

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

        self.serial_number = entry.data[CONF_SERIAL_NUMBER]
        self.device_model = entry.data[CONF_MODEL]
        self.generation = entry.data[CONF_GENERATION]

    async def _async_setup(self) -> None:
        """Fetch device info once on boot."""
        try:
            config_data = await self.api.get_config()
        except TimeOutException as err:
            raise ConfigEntryNotReady(
                f"Device config retrieval timed out: {err}"
            ) from err

        # Cache device information
        device_data = config_data.get("device", {})

        self.firmware_version = device_data.get("fw")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch raw JSON data from the device."""
        sensor_keys = SENSOR_KEYS[self.generation]

        try:
            return await self.api.fetch_data(sensor_keys)
        except TimeOutException as err:
            raise UpdateFailed(f"Device update timed out: {err}") from err

    async def async_push_data(self, sensor_key: str, value: Any) -> bool:
        """Push/write data values to given key on the device."""
        try:
            return await self.api.set_data(sensor_key, value)
        except TimeOutException as err:
            raise HomeAssistantError(f"Device push timed out: {err}") from err
        except (ClientError, ConnectionError, OSError) as err:
            raise HomeAssistantError(f"Device push failed: {err}") from err
