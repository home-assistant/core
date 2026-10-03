"""Coordinator for the HP Printer integration."""

from datetime import timedelta
from typing import override

from aiohpprinter import HpPrinter, HpPrinterData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type HpPrinterConfigEntry = ConfigEntry[HpPrinterDataUpdateCoordinator]

UPDATE_INTERVAL = timedelta(minutes=1)


class HpPrinterDataUpdateCoordinator(DataUpdateCoordinator[HpPrinterData]):
    """Fetch the state of an HP printer."""

    config_entry: HpPrinterConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: HpPrinterConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = HpPrinter(
            config_entry.data[CONF_HOST], async_get_clientsession(hass)
        )

    @override
    async def _async_update_data(self) -> HpPrinterData:
        """Fetch the latest data from the printer."""
        data = await self.client.update()
        # The library swallows errors and reports a printer that does not
        # answer its status endpoint (e.g. powered off) as offline.
        if not data.online:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"host": self.config_entry.data[CONF_HOST]},
            )
        return data
