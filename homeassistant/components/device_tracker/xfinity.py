import logging

from requests.exceptions import RequestException
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST

REQUIREMENTS = ['xfinity-gateway==0.0.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = '10.0.0.1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return an Xfinity Gateway scanner."""
    info = config[DOMAIN]
    host = info.get(CONF_HOST)

    scanner = XfinityDeviceScanner(host)

    return scanner if scanner.success_init else None


class XfinityDeviceScanner(DeviceScanner):
    """This class queries an Xfinity Gateway."""

    def __init__(self, address):
        """Initialize the scanner."""
        from xfinity_gateway import XfinityGateway

        try:
            _LOGGER.debug('Initializing')
            self.gateway = XfinityGateway(address)
            self.gateway.scan_devices()
            self.success_init = True
        except (RequestException, ValueError):
            self.success_init = False
            _LOGGER.error("Unable to connect to gateway. Check host: " + self.gateway.host)

    def scan_devices(self):
        """Scan for new devices and return a list of found MACs."""
        connected_devices = []
        try:
            connected_devices = self.gateway.scan_devices()
        except (RequestException, ValueError):
            _LOGGER.error("Unable to scan devices. Check connection to gateway")
        return connected_devices

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        return self.gateway.get_device_name(device)
