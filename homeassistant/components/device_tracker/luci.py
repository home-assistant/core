"""
Support for OpenWRT (luci) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.luci/
"""
from collections import namedtuple
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SSL)
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['openwrt-luci-rpc==0.3.0']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)

DEFAULT_SSL = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean
})


def get_scanner(hass, config):
    """Validate the configuration and return a Luci scanner."""
    scanner = LuciDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple('Device', ['mac', 'name', 'ip', 'last_update'])


class LuciDeviceScanner(DeviceScanner):
    """This class scans for devices connected to an OpenWrt router."""

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        protocol = 'http' if not config[CONF_SSL] else 'https'
        host_url = '{}://{}'.format(protocol, host)

        from openwrt_luci_rpc import OpenWrtRpc

        self.router = OpenWrtRpc(host_url,
                                 config[CONF_USERNAME],
                                 config[CONF_PASSWORD])

        """Initialize the scanner."""
        self.last_results = []  # type: List[Device]
        self.success_init = self.router.is_logged_in()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [result.name for result in self.last_results if
                        result.mac == device]

        if filter_named:
            return filter_named[0]
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Check the Luci router for devices

        Returns a boolean. True if scan was successful.
        """
        _LOGGER.info("Scanning...")

        result = self.router.get_all_connected_devices(
            only_reachable=True)

        now = dt_util.now()
        last_results = []
        for device in result:
            last_results.append(
                Device(device['macaddress'], device['hostname'],
                       device['ipaddress'], now))

        self.last_results = last_results

        _LOGGER.info("Scan successful")
        return True
