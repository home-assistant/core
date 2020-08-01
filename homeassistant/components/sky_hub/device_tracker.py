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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_HOST): cv.string})


async def async_get_scanner(hass, config):
    """Return a Sky Hub scanner if successful."""
    host = config[DOMAIN].get(CONF_HOST, "192.168.1.254")
    websession = async_get_clientsession(hass)
    hub = SkyQHub(websession, host)

    _LOGGER.debug("Initialising Sky Hub")
    await hub.async_connect()
    if hub.success_init:
        scanner = SkyHubDeviceScanner(hub)
        return scanner

    return None


class SkyHubDeviceScanner(DeviceScanner):
    """This class queries a Sky Hub router."""

    def __init__(self, hub):
        """Initialise the scanner."""
        self._hub = hub
        self.last_results = {}

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._async_update_info()
        return list(self.last_results)

    async def async_get_device_name(self, device):
        """Return the name of the given device."""
        return self.last_results.get(device)

    async def _async_update_info(self):
        """Ensure the information from the Sky Hub is up to date."""
        _LOGGER.debug("Scanning")

        data = await self._hub.async_get_skyhub_data()

        if not data:
            return

        self.last_results = data
