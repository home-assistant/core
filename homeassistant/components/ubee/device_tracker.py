"""Support for Ubee router."""

import logging
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_MODEL = 'model'
DEFAULT_MODEL = 'detect'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return a Ubee scanner."""
    info = config[DOMAIN]
    host = info[CONF_HOST]
    username = info[CONF_USERNAME]
    password = info[CONF_PASSWORD]
    model = info[CONF_MODEL]

    from pyubee import Ubee
    ubee = Ubee(host, username, password, model)
    if not ubee.login():
        _LOGGER.error("Login failed")
        return None

    scanner = UbeeDeviceScanner(ubee)
    return scanner


class UbeeDeviceScanner(DeviceScanner):
    """This class queries a wireless Ubee router."""

    def __init__(self, ubee):
        """Initialize the Ubee scanner."""
        self._ubee = ubee
        self._mac2name = {}

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        devices = self._get_connected_devices()
        self._mac2name = devices
        return list(devices)

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        return self._mac2name.get(device)

    def _get_connected_devices(self):
        """List connected devices with pyubee."""
        if not self._ubee.session_active():
            self._ubee.login()

        return self._ubee.get_connected_devices()
