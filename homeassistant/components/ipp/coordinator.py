"""Coordinator for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyipp import IPP, IPPError, Printer as IPPPrinter

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    CONF_BASE_PATH,
    DOMAIN,
)

PLATFORMS = [SENSOR_DOMAIN]
SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class IPPDataUpdateCoordinator(DataUpdateCoordinator[IPPPrinter]):
    """Class to manage fetching IPP data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        base_path: str,
        tls: bool,
        verify_ssl: bool,
    ) -> None:
        """Initialize global IPP data updater."""
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

    async def _async_update_data(self) -> IPPPrinter:
        """Fetch data from IPP."""
        try:
            return await self.ipp.printer()
        except IPPError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
