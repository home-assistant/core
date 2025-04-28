"""Coordinator for The Internet Printing Protocol (IPP) integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyipp import IPP, IPPError, Printer as IPPPrinter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BASE_PATH, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

type IPPConfigEntry = ConfigEntry[IPPDataUpdateCoordinator]


class IPPDataUpdateCoordinator(DataUpdateCoordinator[IPPPrinter]):
    """Class to manage fetching IPP data from single endpoint."""

    config_entry: IPPConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: IPPConfigEntry) -> None:
        """Initialize global IPP data updater."""
        self.device_id = config_entry.unique_id or config_entry.entry_id
        self.ipp = IPP(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            base_path=config_entry.data[CONF_BASE_PATH],
            tls=config_entry.data[CONF_SSL],
            verify_ssl=config_entry.data[CONF_VERIFY_SSL],
            session=async_get_clientsession(hass, config_entry.data[CONF_VERIFY_SSL]),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> IPPPrinter:
        """Fetch data from IPP."""
        try:
            return await self.ipp.printer()
        except IPPError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
