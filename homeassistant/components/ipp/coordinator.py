"""Coordinator for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyipp import IPP, IPPError, Printer as IPPPrinter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import async_get as dr_async_get
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class IPPDataUpdateCoordinator(DataUpdateCoordinator[IPPPrinter]):
    """Class to manage fetching IPP data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        host: str,
        port: int,
        base_path: str,
        tls: bool,
        verify_ssl: bool,
        device_id: str,
    ) -> None:
        """Initialize global IPP data updater."""
        self.entry = entry
        self.device_id = device_id
        self.initialized = False
        self.ipp = IPP(
            host=host,
            port=port,
            base_path=base_path,
            tls=tls,
            verify_ssl=verify_ssl,
            session=async_get_clientsession(hass, verify_ssl),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _async_update_device_entity(self, data: IPPPrinter) -> None:
        """Update device entity info."""
        dev_reg = dr_async_get(self.hass)
        dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=data.info.manufacturer,
            model=data.info.model,
            name=data.info.name,
            sw_version=data.info.version,
            configuration_url=data.info.more_info,
        )

    async def _async_update_data(self) -> IPPPrinter:
        """Fetch data from IPP."""
        try:
            printer = await self.ipp.printer()

            if not self.initialized:
                self.initialized = True
                self._async_update_device_entity(printer)

            return printer
        except IPPError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
