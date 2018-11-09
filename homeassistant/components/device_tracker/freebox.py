import logging
import asyncio

from collections import namedtuple

from homeassistant.components.freebox import DATA_FREEBOX
from homeassistant.components.device_tracker import DeviceScanner

DEPENDENCIES = ['freebox']

_LOGGER = logging.getLogger(__name__)


async def async_get_scanner(hass, config):
    """Validate the configuration and return a Freebox scanner."""
    scanner = FreeboxDeviceScanner(hass.data[DATA_FREEBOX])
    await scanner.async_connect()
    return scanner if scanner.success_init else None

Device = namedtuple('Device', ['id', 'name', 'ip'])


def _build_device(device_dict):
    return Device(
        device_dict['l2ident']['id'],
        device_dict['primary_name'],
        device_dict['l3connectivities'][0]['addr'])

class FreeboxDeviceScanner(DeviceScanner):

    def __init__(self, fbx):
        """Initialize the scanner."""
        self.last_results = {}
        self.success_init = False
        self.connection = fbx

    async def async_connect(self):
        """Initialize connection to the router."""
        # Test the router is accessible.
        data = await self.connection.lan.get_hosts_list()
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self.async_update_info()
        return [device.id for device in self.last_results]

    async def get_device_name(self, device):
        filter_named = [result.name for result in self.last_results if
                        result.id == device]

        if filter_named:
            return filter_named[0]
        return None

    async def async_update_info(self):
        """Ensure the information from the Freebox router is up to date."""
        _LOGGER.info('Checking Devices')

        hosts = await self.connection.lan.get_hosts_list()

        last_results = [_build_device(device)
                              for device in hosts
                              if device['active']]

        self.last_results = last_results
        return True
