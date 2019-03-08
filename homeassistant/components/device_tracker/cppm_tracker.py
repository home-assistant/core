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
    CONF_HOST, CONF_API_KEY, CONF_SCAN_INTERVAL
)

REQUIREMENTS = ['clearpasspy==1.0.2']

CONF_SCAN_INTERVAL = timedelta(seconds=120)

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
        self._cppm_host = config[CONF_HOST]
        self._api_key = config[CONF_API_KEY]
        self._grant_type = grant_type
        self._client_id = config[CLIENT_ID]
        self.success_init = self.get_cppm_data()

    async def async_scan_devices(self):
        """Initialize scanner."""
        self.get_cppm_data()
        return [device['mac'] for device in self.results]

    async def async_get_device_name(self, device):
        """Retrieve device name."""
        return [device['name'] for device in self.results]

    @Throttle(CONF_SCAN_INTERVAL)
    def get_cppm_data(self):
        """Retrieve data from Aruba Clearpass and return parsed result."""
        from clearpasspy import ClearPass
        data = {
            'server': self._cppm_host,
            'grant_type': self._grant_type,
            'secret': self._api_key,
            'client': self._client_id
        }
        _LOGGER.debug("DATA: %s", data)

        cppm = ClearPass(data)
        endpoints = cppm.get_endpoints(100)['_embedded']['items']
        devices = []
        for item in endpoints:
            if cppm.online_status(item['mac_address']):
                device = {
                    'mac': item['mac_address'],
                    'name': item['mac_address']
                }
                devices.append(device)
            else:
                continue
        self.results = devices
        return True
