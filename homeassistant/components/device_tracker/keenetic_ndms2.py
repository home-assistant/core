"""
Support for Zyxel Keenetic NDMS2 based routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.keenetic_ndms2/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME
)

REQUIREMENTS = ['ndms2_client==0.0.5']

_LOGGER = logging.getLogger(__name__)

# Interface name to track devices for. Most likely one will not need to
# change it from default 'Home'. This is needed not to track Guest WI-FI-
# clients and router itself
CONF_INTERFACE = 'interface'

DEFAULT_INTERFACE = 'Home'
DEFAULT_PORT = 23


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_INTERFACE, default=DEFAULT_INTERFACE): cv.string,
})


def get_scanner(_hass, config):
    """Validate the configuration and return a Nmap scanner."""
    scanner = KeeneticNDMS2DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class KeeneticNDMS2DeviceScanner(DeviceScanner):
    """This class scans for devices using keenetic NDMS2 web interface."""

    def __init__(self, config):
        """Initialize the scanner."""
        from ndms2_client import Client, TelnetConnection
        self.last_results = []

        self._interface = config[CONF_INTERFACE]

        self._client = Client(TelnetConnection(
            config.get(CONF_HOST),
            config.get(CONF_PORT),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
        ))

        self.success_init = self._update_info()
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        name = next((
            result.name for result in self.last_results
            if result.mac == device), None)
        return name

    def get_extra_attributes(self, device):
        """Return the IP of the given device."""
        attributes = next((
            {'ip': result.ip} for result in self.last_results
            if result.mac == device), {})
        return attributes

    def _update_info(self):
        """Get ARP from keenetic router."""
        _LOGGER.debug("Fetching devices from router...")

        from ndms2_client import ConnectionException
        try:
            self.last_results = [
                dev
                for dev in self._client.get_devices()
                if dev.interface == self._interface
            ]
            _LOGGER.debug("Successfully fetched data from router")
            return True

        except ConnectionException:
            _LOGGER.error("Error fetching data from router")
            return False
