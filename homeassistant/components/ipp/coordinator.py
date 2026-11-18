"""Coordinator for The Internet Printing Protocol (IPP) integration."""

from datetime import timedelta
import logging
from typing import override

from pyipp import IPP, IPPError, Printer as IPPPrinter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BASE_PATH, DOMAIN, REQUEST_TIMEOUT

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
            request_timeout=REQUEST_TIMEOUT,
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._printer_unreachable_logged = False

    @override
    async def _async_update_data(self) -> IPPPrinter:
        """Fetch data from IPP."""
        try:
            printer = await self.ipp.printer()
        except IPPError as error:
            if self.data is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_response",
                ) from error

            # The printer was reachable before. Many printers (especially
            # inkjet/laser printers in a home network) are simply switched
            # off or in standby most of the time, which is not an error
            # condition worth surfacing as "unavailable" on every sensor.
            # Keep serving the last known values instead.
            if not self._printer_unreachable_logged:
                _LOGGER.warning(
                    "Could not reach printer, using last known values until "
                    "it is reachable again: %s",
                    error,
                )
                self._printer_unreachable_logged = True

            return self.data

        self._printer_unreachable_logged = False
        return printer
