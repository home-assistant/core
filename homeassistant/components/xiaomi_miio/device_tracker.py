"""Support for Xiaomi Mi WiFi Repeater 2."""

from __future__ import annotations

import logging

from miio import DeviceException, WifiRepeater
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    }
)


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> XiaomiMiioDeviceScanner | None:
    """Return a Xiaomi MiIO device scanner."""
    scanner = None
    config = config[DEVICE_TRACKER_DOMAIN]

    host = config[CONF_HOST]
    token = config[CONF_TOKEN]

    _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

    try:
        device = WifiRepeater(host, token)
        device_info = device.info()
        _LOGGER.debug(
            "%s %s %s detected",
            device_info.model,
            device_info.firmware_version,
            device_info.hardware_version,
        )
        scanner = XiaomiMiioDeviceScanner(device)
    except DeviceException as ex:
        _LOGGER.error("Device unavailable or token incorrect: %s", ex)

    return scanner


class XiaomiMiioDeviceScanner(DeviceScanner):
    """Class which queries a Xiaomi Mi WiFi Repeater."""

    def __init__(self, device):
        """Initialize the scanner."""
        self.device = device

    async def async_scan_devices(self):
        """Scan for devices and return a list containing found device IDs."""
        try:
            station_info = await self.hass.async_add_executor_job(self.device.status)
            _LOGGER.debug("Got new station info: %s", station_info)
        except DeviceException as ex:
            _LOGGER.error("Unable to fetch the state: %s", ex)
            return []

        return [device["mac"] for device in station_info.associated_stations]

    async def async_get_device_name(self, device: str) -> str | None:
        """Return None.

        The repeater doesn't provide the name of the associated device.
        """
        return None
