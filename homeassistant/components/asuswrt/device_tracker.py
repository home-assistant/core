"""Support for ASUSWRT routers."""
import logging

from homeassistant.components.device_tracker import DeviceScanner

from . import DATA_ASUSWRT

_LOGGER = logging.getLogger(__name__)


async def async_get_scanner(hass, config):
    """Validate the configuration and return an ASUS-WRT scanner."""
    scanner = AsusWrtDeviceScanner(hass.data[DATA_ASUSWRT])
    await scanner.async_connect()
    return scanner if scanner.success_init else None


class AsusWrtDeviceScanner(DeviceScanner):
    """This class queries a router running ASUSWRT firmware."""

    # Eighth attribute needed for mode (AP mode vs router mode)
    def __init__(self, api):
        """Initialize the scanner."""
        self.last_results = {}
        self.success_init = False
        self.connection = api

    async def async_connect(self):
        """Initialize connection to the router."""
        # Test the router is accessible.
        data = await self.connection.async_get_connected_devices()
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self.async_update_info()
        return list(self.last_results.keys())

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        return self.last_results[device].name

    async def async_update_info(self):
        """Ensure the information from the ASUSWRT router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("Checking Devices")

        self.last_results = await self.connection.async_get_connected_devices()
