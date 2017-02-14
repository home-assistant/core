"""
Support for Sky Hub.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.sky_hub/
"""
import logging
import re
import threading
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_MAC_REGEX = re.compile(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})')

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string
})


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Return a Sky Hub scanner if successful."""
    scanner = SkyHubDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SkyHubDeviceScanner(DeviceScanner):
    """This class queries a Sky Hub router."""

    def __init__(self, config):
        """Initialise the scanner."""
        _LOGGER.info("Initialising Sky Hub")
        self.host = config.get(CONF_HOST, '192.168.1.254')

        self.lock = threading.Lock()

        self.last_results = {}

        self.url = 'http://{}/'.format(self.host)

        # Test the router is accessible
        data = _get_skyhub_data(self.url)
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
        """Ensure the information from the Sky Hub is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info("Scanning")

            data = _get_skyhub_data(self.url)

            if not data:
                _LOGGER.warning('Error scanning devices')
                return False

            self.last_results = data

            return True


def _get_skyhub_data(url):
    """Retrieve data from Sky Hub and return parsed result."""
    try:
        response = requests.get(url, timeout=5)
    except requests.exceptions.Timeout:
        _LOGGER.exception("Connection to the router timed out")
        return
    if response.status_code == 200:
        return _parse_skyhub_response(response.text)
    else:
        _LOGGER.error("Invalid response from Sky Hub: %s", response)


def _parse_skyhub_response(data_str):
    """Parse the Sky Hub data format."""
    pattmatch = re.search('attach_dev = \'(.*)\'', data_str)
    if pattmatch is None:
        raise IOError('Error: Impossible to fetch data from' +
                      ' Sky Hub. Try to reboot the router.')
    patt = pattmatch.group(1)

    dev = [patt1.split(',') for patt1 in patt.split('<lf>')]

    devices = {}
    for dvc in dev:
        if _MAC_REGEX.match(dvc[1]):
            devices[dvc[1]] = dvc[0]
        else:
            raise RuntimeError('Error: MAC address ' + dvc[1] +
                               ' not in correct format.')

    return devices
