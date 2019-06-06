"""Support for BT Smart Hub (Sometimes referred to as BT Home Hub 6)."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_IP = '192.168.1.254'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): cv.string,
})


def get_scanner(hass, config):
    """Return a BT Smart Hub scanner if successful."""
    scanner = BTSmartHubScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class BTSmartHubScanner(DeviceScanner):
    """This class queries a BT Smart Hub."""

    def __init__(self, config):
        """Initialise the scanner."""
        _LOGGER.debug("Initialising BT Smart Hub")
        self.host = config[CONF_HOST]
        self.last_results = {}
        self.success_init = False

        # Test the router is accessible
        data = self.get_bt_smarthub_data()
        if data:
            self.success_init = True
        else:
            _LOGGER.info("Failed to connect to %s", self.host)

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
        """Ensure the information from the BT Smart Hub is up to date."""
        if not self.success_init:
            return

        _LOGGER.info("Scanning")
        data = self.get_bt_smarthub_data()
        if not data:
            _LOGGER.warning("Error scanning devices")
            return

        clients = [client for client in data.values()]
        self.last_results = clients

    def get_bt_smarthub_data(self):
        """Retrieve data from BT Smart Hub and return parsed result."""
        import btsmarthub_devicelist
        # Request data from bt smarthub into a list of dicts.
        data = btsmarthub_devicelist.get_devicelist(
            router_ip=self.host, only_active_devices=True)
        # Renaming keys from parsed result.
        devices = {}
        for device in data:
            try:
                devices[device['UserHostName']] = {
                    'ip': device['IPAddress'],
                    'mac': device['PhysAddress'],
                    'host': device['UserHostName'],
                    'status': device['Active']
                }
            except KeyError:
                pass
        return devices
