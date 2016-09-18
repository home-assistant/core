"""
Support for BT Home Hub 5.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bt_home_hub_5/
"""
import logging
import re
import threading
from datetime import timedelta
import xml.etree.ElementTree as ET
import json
from urllib.parse import unquote

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST
from homeassistant.util import Throttle

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

_MAC_REGEX = re.compile(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})')

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string
})


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Return a BT Home Hub 5 scanner if successful."""
    scanner = BTHomeHub5DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class BTHomeHub5DeviceScanner(object):
    """This class queries a BT Home Hub 5."""

    def __init__(self, config):
        """Initialise the scanner."""
        _LOGGER.info('Initialising BT Home Hub 5')
        self.host = config.get(CONF_HOST, '192.168.1.254')

        self.lock = threading.Lock()

        self.last_results = {}

        self.url = 'http://{}/nonAuth/home_status.xml'.format(self.host)

        # Test the router is accessible
        data = _get_homehub_data(self.url)
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return (device for device in self.last_results)

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        with self.lock:
            # If not initialised and not already scanned and not found.
            if device not in self.last_results:
                self._update_info()

                if not self.last_results:
                    return None

            return self.last_results.get(device)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the BT Home Hub 5 is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info('Scanning')

            data = _get_homehub_data(self.url)

            if not data:
                _LOGGER.warning('Error scanning devices')
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
    root = ET.fromstring(data_str)

    dirty_json = root.find('known_device_list').get('value')

    # Normalise the JavaScript data to JSON.
    clean_json = unquote(dirty_json.replace('\'', '\"')
                         .replace('{', '{\"')
                         .replace(':\"', '\":\"')
                         .replace('\",', '\",\"'))

    known_devices = [x for x in json.loads(clean_json) if x]

    devices = {}

    for device in known_devices:
        name = device.get('name')
        mac = device.get('mac')

        if _MAC_REGEX.match(mac) or ',' in mac:
            for mac_addr in mac.split(','):
                if _MAC_REGEX.match(mac_addr):
                    devices[mac_addr] = name
        else:
            devices[mac] = name

    return devices
