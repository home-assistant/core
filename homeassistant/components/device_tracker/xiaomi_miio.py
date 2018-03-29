"""
Support for Xiaomi Mi WiFi Repeater 2.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/device_tracker.xiaomi_miio/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (DOMAIN, PLATFORM_SCHEMA,
                                                     DeviceScanner)
from homeassistant.const import (CONF_HOST, CONF_TOKEN)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
})

REQUIREMENTS = ['python-miio==0.3.9']


def get_scanner(hass, config):
    """Return a Xiaomi MiIO device scanner."""
    from miio import WifiRepeater, DeviceException

    scanner = None
    host = config[DOMAIN].get(CONF_HOST)
    token = config[DOMAIN].get(CONF_TOKEN)

    _LOGGER.info(
        "Initializing with host %s (token %s...)", host, token[:5])

    try:
        device = WifiRepeater(host, token)
        device_info = device.info()
        _LOGGER.info("%s %s %s detected",
                     device_info.model,
                     device_info.firmware_version,
                     device_info.hardware_version)
        scanner = XiaomiMiioDeviceScanner(hass, device)
    except DeviceException as ex:
        _LOGGER.error("Device unavailable or token incorrect: %s", ex)

    return scanner


class XiaomiMiioDeviceScanner(DeviceScanner):
    """This class queries a Xiaomi Mi WiFi Repeater."""

    def __init__(self, hass, device):
        """Initialize the scanner."""
        self.device = device

    async def async_scan_devices(self):
        """Scan for devices and return a list containing found device ids."""
        from miio import DeviceException

        devices = []
        try:
            station_info = await self.hass.async_add_job(self.device.status)
            _LOGGER.debug("Got new station info: %s", station_info)

            for device in station_info['mat']:
                devices.append(device['mac'])

        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)

        return devices

    async def async_get_device_name(self, device):
        """The repeater doesn't provide the name of the associated device."""
        return None
