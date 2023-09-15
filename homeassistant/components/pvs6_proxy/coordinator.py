"""DataUpdateCoordinator for the PVOutput integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL
from .interface import Devices, PVOutput


class PVOutputDataUpdateCoordinator(DataUpdateCoordinator[Devices]):
    """The PVOutput Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the PVOutput coordinator."""
        self.config_entry = entry
        self.pvoutput = PVOutput(session=async_get_clientsession(hass))
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> Devices:
        return await self.pvoutput.devices()
