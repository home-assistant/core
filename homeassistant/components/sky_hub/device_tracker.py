"""Support for Sky Hub."""
import logging

from pyskyqhub.skyq_hub import SkyQHub
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_ERROR = logging.ERROR
_INFO = logging.INFO

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_HOST): cv.string})


async def async_get_scanner(hass, config):
    """Return a Sky Hub scanner if successful."""
    host = config[DOMAIN].get(CONF_HOST, "192.168.1.254")
    websession = async_get_clientsession(hass)
    hub = SkyQHub(websession, host)
    scanner = SkyHubDeviceScanner(config[DOMAIN], hub, host)
    await scanner.async_connect(hass)
    return scanner if scanner.success_init else None


class SkyHubDeviceScanner(DeviceScanner):
    """This class queries a Sky Hub router."""

    def __init__(self, config, hub, host):
        """Initialise the scanner."""
        self._connection_failed = False
        self._dataparse_failed = False
        self._hub = hub
        self.host = host
        self.last_results = {}
        self.success_init = False

    async def async_connect(self, hass):
        """Test the router is accessible."""
        _LOGGER.info("Initialising Sky Hub")
        await self._hub.async_connect()
        self.success_init = self._hub.success_init

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._async_update_info()

        return (device for device in self.last_results)

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        if device not in self.last_results:
            await self._async_update_info()

            if not self.last_results:
                return None

        return self.last_results.get(device)

    async def _async_update_info(self):
        """Ensure the information from the Sky Hub is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Scanning")

        data = await self._hub.async_get_skyhub_data()

        if not data:
            return False

        self.last_results = data

        return True
