"""Coordinator for Autarco integration."""

from __future__ import annotations

from typing import NamedTuple

from autarco import (
    AccountSite,
    Autarco,
    AutarcoConnectionError,
    Battery,
    Inverter,
    Site,
    Solar,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class AutarcoData(NamedTuple):
    """Class for defining data in dict."""

    solar: Solar
    inverters: dict[str, Inverter]
    site: Site
    battery: Battery | None


class AutarcoDataUpdateCoordinator(DataUpdateCoordinator[AutarcoData]):
    """Class to manage fetching Autarco data from the API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Autarco,
        account_site: AccountSite,
    ) -> None:
        """Initialize global Autarco data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.account_site = account_site

    async def _async_update_data(self) -> AutarcoData:
        """Fetch data from Autarco API."""
        battery = None
        try:
            site = await self.client.get_site(self.account_site.public_key)
            solar = await self.client.get_solar(self.account_site.public_key)
            inverters = await self.client.get_inverters(self.account_site.public_key)
            if site.has_battery:
                battery = await self.client.get_battery(self.account_site.public_key)
        except AutarcoConnectionError as error:
            raise UpdateFailed(error) from error
        return AutarcoData(
            solar=solar,
            inverters=inverters,
            site=site,
            battery=battery,
        )
