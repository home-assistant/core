"""
Support for ASUSWRT routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.asuswrt/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT, CONF_MODE,
    CONF_PROTOCOL)

REQUIREMENTS = ['aioasuswrt==1.1.2']

_LOGGER = logging.getLogger(__name__)

CONF_PUB_KEY = 'pub_key'
CONF_SSH_KEY = 'ssh_key'
CONF_REQUIRE_IP = 'require_ip'
DEFAULT_SSH_PORT = 22
SECRET_GROUP = 'Password or SSH Key'

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_PASSWORD, CONF_PUB_KEY, CONF_SSH_KEY),
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PROTOCOL, default='ssh'): vol.In(['ssh', 'telnet']),
        vol.Optional(CONF_MODE, default='router'): vol.In(['router', 'ap']),
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
        vol.Optional(CONF_REQUIRE_IP, default=True): cv.boolean,
        vol.Exclusive(CONF_PASSWORD, SECRET_GROUP): cv.string,
        vol.Exclusive(CONF_SSH_KEY, SECRET_GROUP): cv.isfile,
        vol.Exclusive(CONF_PUB_KEY, SECRET_GROUP): cv.isfile
    }))


async def async_get_scanner(hass, config):
    """Validate the configuration and return an ASUS-WRT scanner."""
    scanner = AsusWrtDeviceScanner(config[DOMAIN])
    await scanner.async_connect()
    return scanner if scanner.success_init else None


class AsusWrtDeviceScanner(DeviceScanner):
    """This class queries a router running ASUSWRT firmware."""

    # Eighth attribute needed for mode (AP mode vs router mode)
    def __init__(self, config):
        """Initialize the scanner."""
        from aioasuswrt.asuswrt import AsusWrt

        self.last_results = {}
        self.success_init = False
        self.connection = AsusWrt(config[CONF_HOST], config[CONF_PORT],
                                  config[CONF_PROTOCOL] == 'telnet',
                                  config[CONF_USERNAME],
                                  config.get(CONF_PASSWORD, ''),
                                  config.get('ssh_key',
                                             config.get('pub_key', '')),
                                  config[CONF_MODE], config[CONF_REQUIRE_IP])

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
        _LOGGER.info('Checking Devices')

        self.last_results = await self.connection.async_get_connected_devices()
