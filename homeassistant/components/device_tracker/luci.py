"""
Support for OpenWRT (luci) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.luci/
"""
from collections import namedtuple
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SSL)

REQUIREMENTS = ['openwrt-luci-rpc==0.3.0']

_LOGGER = logging.getLogger(__name__)

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


Device = namedtuple('Device', ['mac', 'name'])


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

        self.last_results = {}
        self.success_init = self.router.is_logged_in()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        name = next((
            result.name for result in self.last_results
            if result.mac == device), None)
        return name

    def _update_info(self):
        """Check the Luci router for devices."""
        result = self.router.get_all_connected_devices(
            only_reachable=True)

        _LOGGER.debug("Luci get_all_connected_devices returned:"
                      " %s", result)

        last_results = []
        for device in result:
            last_results.append(
                Device(device['macaddress'], device['hostname']))

        self.last_results = last_results
