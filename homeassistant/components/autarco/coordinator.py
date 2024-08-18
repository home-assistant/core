"""Coordinator for Autarco integration."""

from __future__ import annotations

from typing import NamedTuple

from autarco import AccountSite, Autarco, Inverter, Solar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class AutarcoData(NamedTuple):
    """Class for defining data in dict."""

    solar: Solar
    inverters: dict[str, Inverter]


class AutarcoDataUpdateCoordinator(DataUpdateCoordinator[AutarcoData]):
    """Class to manage fetching Autarco data from the API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Autarco,
        site: AccountSite,
    ) -> None:
        """Initialize global Autarco data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.site = site

    async def _async_update_data(self) -> AutarcoData:
        """Fetch data from Autarco API."""
        return AutarcoData(
            solar=await self.client.get_solar(self.site.public_key),
            inverters=await self.client.get_inverters(self.site.public_key),
        )
