"""Support Device tracking for TP-Link Omada Controller."""
import logging

import aiohttp

from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.const import CONF_NAME

from .const import DOMAIN as OMADA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Validate the configuration and return a DD-WRT scanner."""
    omada = hass.data[OMADA_DOMAIN][entry.data[CONF_NAME]]
    scanner = TplinkOmadaDeviceScanner(omada)
    await scanner.async_connect()
    try:
        scanner = TplinkOmadaDeviceScanner(omada)
        await scanner.async_connect()
        if not scanner.success_init:
            _LOGGER.warning(
                "Omada device tracker failed at the first connection try."
                "It could be due to bad credentials or just a network issue."
            )
        return scanner
    except Exception:  # pylint: disable=broad-except
        return False
    return True


class TplinkOmadaDeviceScanner(DeviceScanner):
    """This class queries a TP-Link Omada Controller."""

    def __init__(self, omada):
        """Initialize the scanner."""
        self.omada = omada
        self.last_results = {}
        self.success_init = False

    async def async_connect(self):
        """Initialize connection to the router."""
        try:
            self.success_init = await self.async_update_info()
        except aiohttp.ClientError:
            _LOGGER.debug("Exception in %s", self.__class__.__name__)

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found MAC IDs."""
        await self.async_update_info()
        return list(self.last_results.keys())

    def get_device_name(self, device):
        """Get firmware doesn't save the name of the wireless device."""
        return self.last_results.get(device)

    async def async_update_info(self, connection_test=False):
        """Ensure the information from the TP-Link AP is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("Loading wireless clients from Omada Controller...")

        list_of_devices = await self.omada.fetch_clients_list()
        if list_of_devices:
            self.last_results = list_of_devices
            return True

        return False
