"""
Support for Netgear routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.netgear/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT)

REQUIREMENTS = ['pynetgear==0.3.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'routerlogin.net'
DEFAULT_USER = 'admin'
DEFAULT_PORT = 5000

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USER): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port
})


def get_scanner(hass, config):
    """Validate the configuration and returns a Netgear scanner."""
    info = config[DOMAIN]
    host = info.get(CONF_HOST)
    username = info.get(CONF_USERNAME)
    password = info.get(CONF_PASSWORD)
    port = info.get(CONF_PORT)

    scanner = NetgearDeviceScanner(host, username, password, port)

    return scanner if scanner.success_init else None


class NetgearDeviceScanner(DeviceScanner):
    """Queries a Netgear wireless router using the SOAP-API."""

    def __init__(self, host, username, password, port):
        """Initialize the scanner."""
        import pynetgear

        self.last_results = []
        self._api = pynetgear.Netgear(password, host, username, port)

        _LOGGER.info("Logging in")

        results = self._api.get_attached_devices()

        self.success_init = results is not None

        if self.success_init:
            self.last_results = results
        else:
            _LOGGER.error("Failed to Login")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return (device.mac for device in self.last_results)

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        try:
            return next(result.name for result in self.last_results
                        if result.mac == device)
        except StopIteration:
            return None

    def _update_info(self):
        """Retrieve latest information from the Netgear router.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return

        _LOGGER.info("Scanning")

        results = self._api.get_attached_devices()

        if results is None:
            _LOGGER.warning("Error scanning devices")

        self.last_results = results or []
