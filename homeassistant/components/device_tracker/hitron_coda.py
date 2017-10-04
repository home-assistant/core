"""
Support for the Hitron CODA-4582U, provided by Rogers.

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

        self._url = 'http://%s/data/getConnectInfo.asp' % config[CONF_HOST]

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
        """Get ARP from router."""
        _LOGGER.info("Fetching...")

        last_results = []

        # doing a request
        try:
            res = requests.get(self._url, timeout=10, cookies={
                'LANG_COOKIE': 'en_US',
                'cur_modelname': 'CODA-4582U',
                'userName': self._username,
                'password': self._password,
                'userid': '1198377306',  # magic number
                'modelname': 'CODA-4582U',
                'IE8': '0',
                'isEdit2': '0',
                'isEdit3': '0',
                'isEdit': '0',
                'isEdit1': '0',
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
            mac = info.macAddr
            name = info.hostName
            # No address = no item :)
            if mac is None:
                continue

            last_results.append(Device(mac.upper(), name))

        self.last_results = last_results

        _LOGGER.info("Request successful")
        return True
