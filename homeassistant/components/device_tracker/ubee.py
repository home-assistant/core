"""
Support for Ubee router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ubee/
"""
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_ROUTER_REGEX = re.compile(
    r'<tr bgcolor=#[0-9a-fA-F]+>'
    r'<td>([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:'
    r'[0-9a-fA-F]{2}:[0-9a-fA-F]{2})</td>'
    r'<td>\d+</td><td>.+</td><td>\d+\.\d+\.\d+\.\d+</td><td>(.+)</td>'
    r'<td>.+</td><td>\d+</td></tr>'
)
_MAC_REGEX = re.compile(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})')

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})


def get_scanner(hass, config):
    """Validate the configuration and return a Ubee scanner."""
    try:
        return UbeeRouterDeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


class UbeeRouterDeviceScanner(DeviceScanner):
    """This class queries a wireless Ubee router."""
    def __init__(self, config):
        """Initialize the Ubee scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.login_url = 'http://{}/goform/login'.format(self.host)
        self.status_url = 'http://{}/UbeeAdvConnectedDevicesList.asp'.format(
            self.host
        )

        self.last_results = {}
        self.mac2name = {}

        # Test the router is accessible
        payload = {
            'loginUsername': self.username,
            'loginPassword': self.password
        }
        try:
            response = requests.post(self.login_url, data=payload, timeout=4)
        except requests.exceptions.Timeout:
            print('Connection to the router timed out')
            return
        data = response.text
        if not data:
            raise ConnectionError('Cannot connect to Ubee router')

    def scan_devices(self):
        """Scan for new devices and return a list
        with found device MAC address."""
        self._update_info()

        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if device in self.mac2name:
            return self.mac2name.get(device)

        return None

    def _update_info(self):
        """Ensure the information from the router is up to date.
        Return boolean if scanning successful.
        """
        _LOGGER.info("Loading wireless clients...")

        data = self.get_router_data()

        if not data:
            return False

        self.mac2name = data
        self.last_results = []
        self.last_results.extend(item for item in data
                                 if _MAC_REGEX.match(item))

        return True

    def get_router_data(self):
        """Retrieve data from Router and return parsed result."""
        try:
            response = requests.get(self.status_url, timeout=4)
        except requests.exceptions.Timeout:
            _LOGGER.exception("Connection to the router timed out")
            return

        if response.status_code == 200:
            return _parse_router_response(response.text)
        if response.status_code == 401:
            # Authentication error
            _LOGGER.exception("Failed to authenticate, "
                              "check your username and password")
            return
        _LOGGER.error("Invalid response from Router: %s", response)

def _parse_router_response(data_str):
    """Parse the Router response."""
    return {
        key: val for key, val in _ROUTER_REGEX.findall(data_str)
    }
