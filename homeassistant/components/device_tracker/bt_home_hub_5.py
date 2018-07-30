"""
Support for BT Home Hub 5.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bt_home_hub_5/
"""

import logging
import re

import requests
from html_table_extractor import HTMLParser

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.device_tracker import (DOMAIN, PLATFORM_SCHEMA,
                                                     DeviceScanner)
from homeassistant.const import CONF_HOST

REQUIREMENTS = ['html-table-parser-python3==0.1.2']

_LOGGER = logging.getLogger(__name__)
_MAC_REGEX = re.compile(r'(([0-9A-Fa-f]{1,2}:){5}[0-9A-Fa-f]{1,2})')

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string
})


# pylint: disable=unused-argument
def get_scanner(config):
    """Return a BT Home Hub 5 scanner if successful."""
    scanner = BTHomeHub5DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class BTHomeHub5DeviceScanner(DeviceScanner):
    """This class queries a BT Home Hub 5."""

    def __init__(self, config):
        """Initialise the scanner."""
        _LOGGER.info("Initialising BT Home Hub 5")
        self.host = config.get(CONF_HOST, '192.168.1.254')
        self.last_results = {}
        self.url = 'http://{}/'.format(self.host)

        # Test the router is accessible
        data = _get_homehub_data(self.url)
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return (device for device in self.last_results)

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        if device not in self.last_results:
            self._update_info()

            if not self.last_results:
                return None

        return self.last_results.get(device)

    def _update_info(self):
        """Ensure the information from the BT Home Hub 5 is up to date.
        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Scanning")

        data = _get_homehub_data(self.url)

        if not data:
            _LOGGER.warning("Error scanning devices")
            return False

        self.last_results = data

        return True


def _get_homehub_data(url):
    """Retrieve data from BT Home Hub 5 and return parsed result."""
    try:
        response = requests.get(url, timeout=5)
    except requests.exceptions.Timeout:
        _LOGGER.exception("Connection to the router timed out")
        return
    if response.status_code == 200:
        return _parse_homehub_response(response.text)
    else:
        _LOGGER.error("Invalid response from Home Hub: %s", response)


def _parse_homehub_response(data_str):
    """Parse the BT Home Hub 5 data format."""

    p = HTMLTableParser()
    p.feed(data_str)

    known_devices = p.tables[9]

    devices = {}

    for device in known_devices:
        if len(device) == 5 and device[2] != '':
            devices[device[2]] = device[1]

    return devices
