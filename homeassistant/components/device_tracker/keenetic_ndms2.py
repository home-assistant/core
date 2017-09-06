"""
Support for Zyxel Keenetic NDMS2 based routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.keenetic_ndms2/
"""
from datetime import timedelta
import logging

import requests
from collections import namedtuple

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD
)

_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE = 'exclude'
# Interval in minutes to assume these hosts are still home
CONF_HOME_INTERVAL = 'home_interval'
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
    vol.Required(CONF_HOME_INTERVAL, default=0): cv.positive_int,
    vol.Optional(CONF_EXCLUDE, default=[]):
        vol.All(cv.ensure_list, vol.Length(min=1)),
})


def get_scanner(_hass, config):
    """Validate the configuration and return a Nmap scanner."""
    scanner = KeeneticNDMS2DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple('Device', ['mac', 'name', 'ip', 'last_update'])


class KeeneticNDMS2DeviceScanner(DeviceScanner):
    """This class scans for devices using keenetic NDMS2 web interface."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []

        self._url = 'http://%s/rci/show/ip/arp' % config[CONF_HOST]
        self._interface = config[CONF_INTERFACE]
        self._exclude = config[CONF_EXCLUDE]
        self._home_interval = timedelta(minutes=config[CONF_HOME_INTERVAL])

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
        """Get ARP from keenetic router
        """
        _LOGGER.info("Fetching...")

        if self._home_interval:
            boundary = dt_util.now() - self._home_interval
            last_results = [device for device in self.last_results
                            if device.last_update > boundary]
            if last_results:
                exclude_hosts = self._exclude + [device.ip for device
                                                 in last_results]
            else:
                exclude_hosts = self._exclude
        else:
            last_results = []
            exclude_hosts = self._exclude

        # doing a request
        try:
            from requests.auth import HTTPDigestAuth
            res = requests.get(self._url, timeout=10, auth=HTTPDigestAuth(
                self._username, self._password
            ))
        except requests.exceptions.Timeout:
            _LOGGER.exception(
                "Connection to the router timed out at URL %s", self._url)
            return False
        if res.status_code != 200:
            _LOGGER.exception(
                "Connection failed with http code %s", res.status_code)
            return False
        try:
            result = res.json()
        except ValueError:
            # If json decoder could not parse the response
            _LOGGER.exception("Failed to parse response from router")
            return False

        # parsing response
        now = dt_util.now()
        for info in result:
            if info.get('interface') != self._interface:
                continue
            mac = info.get('mac')
            ipv4 = info.get('ip')
            # No address = no item :)
            if mac is None or ipv4 is None:
                continue
            # exclusions
            if ipv4 in exclude_hosts:
                continue

            name = info.get('name')
            last_results.append(Device(mac.upper(), name, ipv4, now))

        self.last_results = last_results

        _LOGGER.info("Request successful")
        return True
