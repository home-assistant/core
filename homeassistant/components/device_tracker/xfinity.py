"""Support for device tracking via Xfinity Gateways."""
import logging

from requests.exceptions import RequestException
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST

REQUIREMENTS = ['xfinity-gateway==0.0.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = '10.0.0.1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return an Xfinity Gateway scanner."""
    from xfinity_gateway import XfinityGateway

    gateway = XfinityGateway(config[DOMAIN][CONF_HOST])
    scanner = None
    try:
        gateway.scan_devices()
        scanner = XfinityDeviceScanner(gateway)
    except (RequestException, ValueError):
        _LOGGER.error("Error communicating with Xfinity Gateway. "
                      "Check host: %s", gateway.host)

    return scanner


class XfinityDeviceScanner(DeviceScanner):
    """This class queries an Xfinity Gateway."""

    def __init__(self, gateway):
        """Initialize the scanner."""
        self.gateway = gateway

    def scan_devices(self):
        """Scan for new devices and return a list of found MACs."""
        connected_devices = []
        try:
            connected_devices = self.gateway.scan_devices()
        except (RequestException, ValueError):
            _LOGGER.error("Unable to scan devices. "
                          "Check connection to gateway")
        return connected_devices

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        return self.gateway.get_device_name(device)
