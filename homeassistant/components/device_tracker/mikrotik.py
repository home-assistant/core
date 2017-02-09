"""
Support for Mikrotik routers.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mikrotik/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import Throttle

REQUIREMENTS = ['tikapy==0.2.1']

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default='192.168.88.1'): cv.string,
    vol.Optional(CONF_PASSWORD, default='admin'): cv.string,
    vol.Optional(CONF_USERNAME, default=''): cv.string
})

def get_scanner(hass, config):
    """Validate the configuration and return MTikScanner."""
    scanner = MTikScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


class MTikScanner(DeviceScanner):
    """This class queries a Mikrotik router."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.success_init = True

        # pylint: disable=import-error
        from tikapy import TikapyClient

        # Establish a connection to the Mikrotik router.
        try:
            self.client = TikapyClient(self.host, 8728)
            self.client.login(self.username, self.password)
            resource = self.client.talk(['/system/resource/getall'])
            if resource == {}:
                self.connected = True
        except (ValueError, TypeError):
            self.client = None

        # At this point it is difficult to tell if a connection is established.
        # So just check for null objects.
        if self.client is None or not self.connected:
            self.success_init = False

        if self.success_init:
            _LOGGER.info('Successfully connected to Mikrotik device')
            self._update_info()
        else:
            _LOGGER.error('Failed to establish connection to Mikrotik device with IP: %s', self.host)

    def scan_devices(self):
        self._update_info()
        active_hosts = []
        for device in self.last_results:
            dev = self.last_results[device]
            if "active-mac-address" in dev:
                active_hosts.append(dev["active-mac-address"])
        return active_hosts

    def get_device_name(self, mac):
        for device in self.last_results:
            dev = self.last_results[device]
            if "active-mac-address" in dev:
                if dev["active-mac-address"] == mac:
                    if "comment" in dev:
                        return dev['comment']
                    elif "host-name" in dev and dev["host-name"] != {}:
                        return dev['host-name']
                    else:
                        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Retrieve latest information from the Mikrotik box."""
        if not self.success_init:
            return False

        _LOGGER.info('Polling')
        self.last_results = self.client.talk(['/ip/dhcp-server/lease/getall'])
        return True
