"""
Support for the Hitron CODA-4582U, provided by Rogers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.hitron_coda/
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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def get_scanner(_hass, config):
    """Validate the configuration and return a Nmap scanner."""
    scanner = HitronCODADeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple('Device', ['mac', 'name'])


class HitronCODADeviceScanner(DeviceScanner):
    """This class scans for devices using the CODA's web interface."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []
        host = config[CONF_HOST]
        self._url = 'http://{}/data/getConnectInfo.asp'.format(host)
        self._loginurl = 'http://{}/goform/login'.format(host)

        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)

        self._userid = None

        self.success_init = self._update_info()
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the device with the given MAC address."""
        name = next((
            result.name for result in self.last_results
            if result.mac == device), None)
        return name

    def _login(self):
        """Log in to the router. This is required for subsequent api calls."""
        _LOGGER.info("Logging in to CODA...")

        try:
            data = [
                ('user', self._username),
                ('pws', self._password),
            ]
            res = requests.post(self._loginurl, data=data, timeout=10)
        except requests.exceptions.Timeout:
            _LOGGER.error(
                "Connection to the router timed out at URL %s", self._url)
            return False
        if res.status_code != 200:
            _LOGGER.error(
                "Connection failed with http code %s", res.status_code)
            return False
        try:
            self._userid = res.cookies['userid']
            return True
        except KeyError:
            _LOGGER.error("Failed to log in to router")
            return False

    def _update_info(self):
        """Get ARP from router."""
        _LOGGER.info("Fetching...")

        if self._userid is None:
            if not self._login():
                _LOGGER.error("Could not obtain a user ID from the router")
                return False
        last_results = []

        # doing a request
        try:
            res = requests.get(self._url, timeout=10, cookies={
                'userid': self._userid
            })
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
            mac = info['macAddr']
            name = info['hostName']
            # No address = no item :)
            if mac is None:
                continue

            last_results.append(Device(mac.upper(), name))

        self.last_results = last_results

        _LOGGER.info("Request successful")
        return True
