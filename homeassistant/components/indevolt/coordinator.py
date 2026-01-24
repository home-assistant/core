"""Home Assistant integration for Indevolt device."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from indevolt_api import IndevoltAPI, TimeOutException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = 30

type IndevoltConfigEntry = ConfigEntry[IndevoltCoordinator]


class IndevoltCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching and pushing data to indevolt devices."""

    config_entry: IndevoltConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
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

        self.device_info_data: dict[str, Any] = {}
        self._initial_sensor_keys: list[str] = []

    def set_initial_sensor_keys(self, keys: list[str]) -> None:
        """Set the initial sensor keys for first data fetch before entities are created."""
        self._initial_sensor_keys = keys

    def _get_api_keys(self) -> list[str]:
        """Get sensor keys from registered contexts or fall back to initial keys."""
        api_keys = list(self.async_contexts())

        # Use initial_sensor_keys for first refresh (before sensor creation)
        if not api_keys:
            api_keys = self._initial_sensor_keys
        return api_keys

    async def async_initialize(self) -> None:
        """Fetch device info once on boot."""
        try:
            config_data = await self.api.get_config()
        except TimeOutException as err:
            raise ConfigEntryNotReady(
                f"Device config retrieval timed out: {err}"
            ) from err
        except Exception as err:
            raise ConfigEntryNotReady(f"Device config retrieval failed: {err}") from err

        device_data = config_data.get("device", {})

        # Cache device information
        self.device_info_data = {
            "sn": device_data.get("sn"),
            "device_model": device_data.get("type"),
            "fw_version": device_data.get("fw"),
            "generation": device_data.get("generation", 1),
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch raw JSON data from the device."""
        sensor_keys = self._get_api_keys()
        if not sensor_keys:
            return {}

        try:
            return await self.api.fetch_data(sensor_keys)
        except TimeOutException as err:
            raise UpdateFailed(f"Device update timed out: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Device update failed: {err}") from err
