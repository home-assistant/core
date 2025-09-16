"""Coordinator for solarman integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

# from solarman_opendata import Solarman
from .solarman import Solarman

_LOGGER = logging.getLogger(__name__)

type SolarmanConfigEntry = ConfigEntry[SolarmanDeviceUpdateCoordinator]


class SolarmanDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for managing Solarman device data updates and control operations."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Solarman device coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )

        # Initialize the API client for communicating with the Solarman device.
        self.api = Solarman(
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
            # Fetch latest data from the physical device
            data = await self.api.fetch_data()
            # Update the coordinator's data store
            self.data = data
        except ConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from e
        else:
            return data

    async def set_power_state(self, active: bool):
        """Change the device's state.

        Args:
            active: True to turn device on, False to turn off
        """
        await self.api.set_status(active)
