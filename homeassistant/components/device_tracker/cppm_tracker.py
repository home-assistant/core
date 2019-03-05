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

SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required('client_id'): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """Initialize Scanner."""
    grant_type = 'client_credentials'
    new_scan = CPPMDeviceScanner(config[DOMAIN], grant_type)
    return new_scan if new_scan.success_init else None


class CPPMDeviceScanner(DeviceScanner):
    """Initialize class."""

    def __init__(self, config, grant_type):
        """Initialize class."""
        _LOGGER.debug("-------------INIT CALLED--------------")
        self._cppm_host = config[CONF_HOST]
        self._api_key = config[CONF_API_KEY]
        self._grant_type = grant_type
        self._client_id = config['client_id']
        self.success_init = self.get_cppm_data()

    async def async_scan_devices(self):
        """Initialize scanner."""
        _LOGGER.debug("------ SCAN DEVICES CALLED. ------------")
        self.get_cppm_data()
        return [device['mac'] for device in self.results]

    async def async_get_device_name(self, device):
        """Retrieve device name."""
        _LOGGER.debug("------ RESOLVING DEVICE NAME ----")
        return [device['name'] for device in self.results]

    @Throttle(CONF_SCAN_INTERVAL)
    def get_cppm_data(self):
        """Retrieve data from Aruba Clearpass and return parsed result."""
        from clearpasspy import ClearPass
        _LOGGER.debug("--------- GET CPPM DATA CALLED------------")
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
        _LOGGER.debug("-----------Update successful!-----------")
        self.results = devices
        return True
