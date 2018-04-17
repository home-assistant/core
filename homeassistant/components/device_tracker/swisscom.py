"""
Support for Swisscom routers (Internet-Box).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.swisscom/
"""
import logging

from aiohttp.hdrs import CONTENT_TYPE
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = '192.168.1.1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string
})


def get_scanner(hass, config):
    """Return the Swisscom device scanner."""
    scanner = SwisscomDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SwisscomDeviceScanner(DeviceScanner):
    """This class queries a router running Swisscom Internet-Box firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.last_results = {}

        # Test the router is accessible.
        data = self.get_swisscom_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client['mac'] for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client['mac'] == device:
                return client['host']
        return None

    def _update_info(self):
        """Ensure the information from the Swisscom router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Loading data from Swisscom Internet Box")
        data = self.get_swisscom_data()
        if not data:
            return False

        active_clients = [client for client in data.values() if
                          client['status']]
        self.last_results = active_clients
        return True

    def get_swisscom_data(self):
        """Retrieve data from Swisscom and return parsed result."""
        url = 'http://{}/ws'.format(self.host)
        headers = {CONTENT_TYPE: 'application/x-sah-ws-4-call+json'}
        data = """
        {"service":"Devices", "method":"get",
        "parameters":{"expression":"lan and not self"}}"""

        request = requests.post(url, headers=headers, data=data, timeout=10)

        devices = {}
        for device in request.json()['status']:
            try:
                devices[device['Key']] = {
                    'ip': device['IPAddress'],
                    'mac': device['PhysAddress'],
                    'host': device['Name'],
                    'status': device['Active']
                    }
            except (KeyError, requests.exceptions.RequestException):
                pass
        return devices
