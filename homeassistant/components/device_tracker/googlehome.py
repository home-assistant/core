"""
Support for Google Home bluetooth tacker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.googlehome/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST

REQUIREMENTS = ['ghlocalapi==0.3.5']

_LOGGER = logging.getLogger(__name__)

CONF_RSSI_THRESHOLD = 'rssi_threshold'

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_RSSI_THRESHOLD, default=-70): vol.Coerce(int),
    }))


async def async_get_scanner(hass, config):
    """Validate the configuration and return an Google Home scanner."""
    scanner = GoogleHomeDeviceScanner(hass, config[DOMAIN])
    await scanner.async_connect()
    return scanner if scanner.success_init else None


class GoogleHomeDeviceScanner(DeviceScanner):
    """This class queries a Google Home unit."""

    def __init__(self, hass, config):
        """Initialize the scanner."""
        from ghlocalapi.device_info import DeviceInfo
        from ghlocalapi.bluetooth import Bluetooth

        self.last_results = {}

        self.success_init = False
        self._host = config[CONF_HOST]
        self.rssi_threshold = config[CONF_RSSI_THRESHOLD]

        session = async_get_clientsession(hass)
        self.deviceinfo = DeviceInfo(hass.loop, session, self._host)
        self.scanner = Bluetooth(hass.loop, session, self._host)

    async def async_connect(self):
        """Initialize connection to Google Home."""
        await self.deviceinfo.get_device_info()
        data = self.deviceinfo.device_info
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self.async_update_info()
        return list(self.last_results.keys())

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        return '{}_{}'.format(self._host,
                              self.last_results[device]['btle_mac_address'])

    async def get_extra_attributes(self, device):
        """Return the extra attributes of the device."""
        return self.last_results[device]

    async def async_update_info(self):
        """Ensure the information from Google Home is up to date."""
        _LOGGER.debug('Checking Devices...')
        await self.scanner.scan_for_devices()
        await self.scanner.get_scan_result()
        ghname = self.deviceinfo.device_info['name']
        devices = {}
        for device in self.scanner.devices:
            if device['rssi'] > self.rssi_threshold:
                uuid = '{}_{}'.format(self._host, device['mac_address'])
                devices[uuid] = {}
                devices[uuid]['rssi'] = device['rssi']
                devices[uuid]['btle_mac_address'] = device['mac_address']
                devices[uuid]['ghname'] = ghname
                devices[uuid]['source_type'] = 'bluetooth'
        await self.scanner.clear_scan_result()
        self.last_results = devices
