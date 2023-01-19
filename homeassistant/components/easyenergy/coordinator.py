"""The Coordinator for easyEnergy."""
from __future__ import annotations

from typing import NamedTuple

from easyenergy import EasyEnergy, Electricity, Gas

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class EasyEnergyData(NamedTuple):
    """Class for defining data in dict."""

    energy_useage_today: Electricity
    energy_return_today: Electricity
    gas_useage_today: Gas | None


class EasyEnergyDataUpdateCoordinator(DataUpdateCoordinator[EasyEnergyData]):
    """Class to manage fetching easyEnergy data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(self, hass) -> None:
        """Initialize global easyEnergy data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.easyenergy = EasyEnergy(session=async_get_clientsession(hass))

    async def _async_update_data(self) -> EasyEnergyData:
        """Fetch data from easyEnergy."""
        today = dt.now().date()
        gas_today = None
        energy_tomorrow = None
