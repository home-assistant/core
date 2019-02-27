"""
Support for Cisco Mobility Express.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/device_tracker.cisco_mobility_express/
"""
import logging
from collections import namedtuple
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SSL, CONF_VERIFY_SSL)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


def get_scanner(hass, config):
    """Validate the configuration and return a Cisco ME scanner."""
    scanner = CiscoMEDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class CiscoMEDeviceScanner(DeviceScanner):
    """This class scans for devices associated to a Cisco ME controller."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.protocol = 'https' if config[CONF_SSL] else 'http'
        self.verify_ssl = config[CONF_VERIFY_SSL]
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.last_results = {}
        self.success_init = self.get_data() is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.macaddr for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        name = next((
            result.Name for result in self.last_results
            if result.macaddr == device), None)
        return name

    def get_extra_attributes(self, device):
        """
        Get extra attributes of a device.

        Some known extra attributes that may be returned in the device tuple
        include SSID, PT (eg 802.11ac), devtype (eg iPhone 7) among others.
        """
        device = next((
            result for result in self.last_results
            if result.macaddr == device), None)
        return device._asdict()

    def _update_info(self):
        """Check the Cisco ME controller for devices."""
        self.last_results = self.get_data()
        _LOGGER.debug("Cisco ME returned:"
                      " %s", self.last_results)

    def get_data(self):
        """Retrieve data from Cisco ME and return parsed result."""
        results_list = []
        url = '{}://{}/data/client-table.html'.format(
            self.protocol, self.host)
        response = requests.get(
            url, auth=(self.username, self.password),
            verify=self.verify_ssl)

        if response.status_code == 200:
            result = response.json()
            for device_entry in result['data']:
                device_entry['controller'] = self.host
                device = namedtuple("Device", device_entry.keys())(
                    *device_entry.values())
                results_list.append(device)
            return results_list
        return None
