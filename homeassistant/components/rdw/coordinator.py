"""Data update coordinator for RDW."""

from __future__ import annotations

from vehicle import RDW, Vehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LICENSE_PLATE, DOMAIN, LOGGER, SCAN_INTERVAL


class RDWDataUpdateCoordinator(DataUpdateCoordinator[Vehicle]):
    """Class to manage fetching RDW data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_APK",
            update_interval=SCAN_INTERVAL,
        )
        self._rdw = RDW(
            session=async_get_clientsession(hass),
            license_plate=config_entry.data[CONF_LICENSE_PLATE],
        )

    async def _async_update_data(self) -> Vehicle:
        """Fetch data from RDW."""
        return await self._rdw.vehicle()
