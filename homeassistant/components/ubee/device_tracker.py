"""
Support for Ubee router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ubee/
"""

import logging
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyubee==0.2']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})


def get_scanner(hass, config):
    """Validate the configuration and return a Ubee scanner."""
    try:
        return UbeeDeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


class UbeeDeviceScanner(DeviceScanner):
    """This class queries a wireless Ubee router."""

    def __init__(self, config):
        """Initialize the Ubee scanner."""
        from pyubee import Ubee

        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.last_results = {}
        self.mac2name = {}

        self.ubee = Ubee(self.host, self.username, self.password)
        _LOGGER.info("Logging in")
        results = self.get_connected_devices()
        self.success_init = results is not None

        if self.success_init:
            self.last_results = results
        else:
            _LOGGER.error("Login failed")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if device in self.mac2name:
            return self.mac2name.get(device)

        return None

    def _update_info(self):
        """Retrieve latest information from the Ubee router."""
        if not self.success_init:
            return

        _LOGGER.debug("Scanning")
        results = self.get_connected_devices()

        if results is None:
            _LOGGER.warning("Error scanning devices")
            return

        self.last_results = results or []

    def get_connected_devices(self):
        """List connected devices with pyubee."""
        if not self.ubee.session_active():
            self.ubee.login()

        return self.ubee.get_connected_devices()
