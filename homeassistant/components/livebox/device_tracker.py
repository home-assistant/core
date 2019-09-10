"""Support for Livebox devices."""
from collections import namedtuple
import logging

from homeassistant.components.device_tracker import DeviceScanner
import homeassistant.util.dt as dt_util

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """Validate the configuration and return a Livebox scanner."""

    scanner = LiveboxDeviceScanner(hass.data[DOMAIN])
    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["mac", "name", "ip", "last_update"])


class LiveboxDeviceScanner(DeviceScanner):
    """Queries the Livebox device."""

    def __init__(self, box):
        """Initialize the scanner."""

        self._box = box
        self.last_results = []
        self.success_init = self.async_update_info()

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""

        await self.async_update_info()
        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""

        filter_named = [
            result.name for result in self.last_results if result.mac == device
        ]
        if filter_named:
            return filter_named[0]
        return None

    async def async_update_info(self):
        """Ensure the information from the Livebox router is up to date."""

        result = (await self._box.system.get_devices())["status"]
        now = dt_util.now()
        last_results = []
        for device in result:
            if device["Active"] and "IPAddress" in device:
                last_results.append(
                    Device(
                        device["PhysAddress"], device["Name"], device["IPAddress"], now
                    )
                )
        self.last_results = last_results
        return True
