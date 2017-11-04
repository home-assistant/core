"""
Support for Zyxel Keenetic NDMS2 based routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.keenetic_ndms2/
"""
import logging
from collections import namedtuple

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME
)

_LOGGER = logging.getLogger(__name__)

# Interface name to track devices for. Most likely one will not need to
# change it from default 'Home'. This is needed not to track Guest WI-FI-
# clients and router itself
CONF_INTERFACE = 'interface'

DEFAULT_INTERFACE = 'Home'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_INTERFACE, default=DEFAULT_INTERFACE): cv.string,
})


def get_scanner(_hass, config):
    """Validate the configuration and return a Nmap scanner."""
    scanner = KeeneticNDMS2DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple('Device', ['mac', 'name'])


class KeeneticNDMS2DeviceScanner(DeviceScanner):
    """This class scans for devices using keenetic NDMS2 web interface."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []

        self._url = 'http://%s/rci/show/ip/arp' % config[CONF_HOST]
        self._interface = config[CONF_INTERFACE]

        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)

        self.success_init = self._update_info()
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]

        if filter_named:
            return filter_named[0]
        return None

    def _update_info(self):
        """Get ARP from keenetic router."""
        _LOGGER.info("Fetching...")

        last_results = []

        # doing a request
        try:
            from requests.auth import HTTPDigestAuth
            res = requests.get(self._url, timeout=10, auth=HTTPDigestAuth(
                self._username, self._password
            ))
        except requests.exceptions.Timeout:
            _LOGGER.error(
                "Connection to the router timed out at URL %s", self._url)
            return False
        if res.status_code != 200:
            _LOGGER.error(
                "Connection failed with http code %s", res.status_code)
            return False
        try:
            result = res.json()
        except ValueError:
            # If json decoder could not parse the response
            _LOGGER.error("Failed to parse response from router")
            return False

        # parsing response
        for info in result:
            if info.get('interface') != self._interface:
                continue
            mac = info.get('mac')
            name = info.get('name')
            # No address = no item :)
            if mac is None:
                continue

            last_results.append(Device(mac.upper(), name))

        self.last_results = last_results

        _LOGGER.info("Request successful")
        return True
