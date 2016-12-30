"""
homeassistant.components.device_tracker.tado.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports presence detection.
The detection is based on geofencing enabled devices used with Tado.
Tado is a Smart Thermostat device.
"""
import logging
from datetime import timedelta
from collections import namedtuple

import requests
import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN, PLATFORM_SCHEMA

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})

REQUIREMENTS = []


def get_scanner(hass, config):
    """Validate config and returns a Tado scanner."""
    info = config[DOMAIN]

    if info.get(CONF_USERNAME) is None or info.get(CONF_PASSWORD) is None:
        _LOGGER.warning('Cannot find username or password')
        return None

    scanner = TadoDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["mac", "name"])


class TadoDeviceScanner(object):
    """This class gets geofenced devices from Tado."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []

        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.tadoapiurl = 'https://my.tado.com/api/v2/me'

        self.success_init = self._update_info()
        _LOGGER.info("Tado scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list containing found device ids."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]

        if filter_named:
            return filter_named[0]
        else:
            return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Query Tado for device marked as at home.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Requesting Tado")

        last_results = []
        credentials = {'username': self.username, 'password': self.password}
        tadoresponse = requests.get(self.tadoapiurl, params=credentials)

        # If response was not successful, raise exception
        tadoresponse.raise_for_status()

        tadojson = tadoresponse.json()

        # Find devices that have geofencing enabled, and are currently at home
        for mobiledevice in tadojson['mobileDevices']:
            if 'location' in mobiledevice:
                if mobiledevice['location']['atHome']:
                    deviceid = mobiledevice['id']
                    devicename = mobiledevice['name']
                    last_results.append(Device(deviceid, devicename))

        self.last_results = last_results

        _LOGGER.info("Tado presence query successful")
        return True
