"""Coordinator for indevolt integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .indevolt import KEYS_GEN1, KEYS_GEN2, Indevolt
from .utils import get_device_gen

_LOGGER = logging.getLogger(__name__)

type IndevoltConfigEntry = ConfigEntry[IndevoltDeviceUpdateCoordinator]


class IndevoltDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for managing Indevolt device data updates and control operations."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Indevolt device coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )

        # Initialize the API client for communicating with the Indevolt device.
        self.api = Indevolt(
            async_get_clientsession(hass),
            config_entry.data["host"],
            config_entry.data["port"],
        )

    async def _async_update_data(self):
        """Fetch and update device data.

        This is automatically called by the DataUpdateCoordinator framework
        according to the defined update_interval.
        """
        try:
            data = {}
            if get_device_gen(self.config_entry.data["model"]) == 1:
                data = await self.api.fetch_all_data(KEYS_GEN1)
            else:
                data = await self.api.fetch_all_data(KEYS_GEN2)
            self.data = data

        except ConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from e
        else:
            return data
