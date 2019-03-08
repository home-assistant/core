"""
Support for ClearPass Policy Manager.

Allows tracking devices with CPPM.
"""
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DeviceScanner, DOMAIN
)
from homeassistant.const import (
    CONF_HOST, CONF_API_KEY
)

REQUIREMENTS = ['clearpasspy==1.0.2']

SCAN_INTERVAL = timedelta(seconds=120)

CLIENT_ID = 'client_id'

GRANT_TYPE = 'client_credentials'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CLIENT_ID): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """Initialize Scanner."""
    new_scan = CPPMDeviceScanner(config[DOMAIN], GRANT_TYPE)
    return new_scan if new_scan.success_init else None


class CPPMDeviceScanner(DeviceScanner):
    """Initialize class."""

    def __init__(self, config, grant_type):
        """Initialize class."""
        from clearpasspy import ClearPass

        data = {
            'server': config[CONF_HOST],
            'grant_type': grant_type,
            'secret': config[CONF_API_KEY],
            'client': config[CLIENT_ID]
        }
        self.cppm = ClearPass(data)

        self.success_init = self.get_cppm_data()

    def scan_devices(self):
        """Initialize scanner."""
        self.get_cppm_data()
        return [device['mac'] for device in self.results]

    def get_device_name(self, device):
        """Retrieve device name."""
        return [device['name'] for device in self.results]

    @Throttle(SCAN_INTERVAL)
    def get_cppm_data(self):
        """Retrieve data from Aruba Clearpass and return parsed result."""
        _LOGGER.debug("Access Token: %s", self.cppm.access_token)

        endpoints = self.cppm.get_endpoints(100)['_embedded']['items']
        devices = []
        for item in endpoints:
            if self.cppm.online_status(item['mac_address']):
                device = {
                    'mac': item['mac_address'],
                    'name': item['mac_address']
                }
                devices.append(device)
            else:
                continue
        self.results = devices
        if self.results is None:
            return False
        else:
            return True
