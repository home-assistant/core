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

REQUIREMENTS = ['pyubee==0.3']

_LOGGER = logging.getLogger(__name__)

CONF_MODEL = 'model'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_MODEL): cv.string,
})


def get_scanner(hass, config):
    """Validate the configuration and return a Ubee scanner."""
    info = config[DOMAIN]
    host = info.get(CONF_HOST)
    username = info.get(CONF_USERNAME)
    password = info.get(CONF_PASSWORD)
    model = info.get(CONF_MODEL)

    scanner = UbeeDeviceScanner(host, username, password, model)

    return scanner if scanner.success_init else None


class UbeeDeviceScanner(DeviceScanner):
    """This class queries a wireless Ubee router."""

    def __init__(self, host, username, password, model):
        """Initialize the Ubee scanner."""
        from pyubee import Ubee

        self.last_results = {}
        self.mac2name = {}

        self.ubee = Ubee(host, username, password, model)

        self.success_init = self.ubee.login()

        if not self.success_init:
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
        results = self._get_connected_devices()

        if results is None:
            _LOGGER.warning("Error scanning devices")
            return

        self.last_results = results or []

    def _get_connected_devices(self):
        """List connected devices with pyubee."""
        if not self.ubee.session_active():
            self.ubee.login()

        return self.ubee.get_connected_devices()
