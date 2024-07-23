"""Support for BT Home Hub 5."""

from __future__ import annotations

import logging

import bthomehub5_devicelist
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_IP = "192.168.1.254"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): cv.string}
)


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> BTHomeHub5DeviceScanner | None:
    """Return a BT Home Hub 5 scanner if successful."""
    scanner = BTHomeHub5DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class BTHomeHub5DeviceScanner(DeviceScanner):
    """Class which queries a BT Home Hub 5."""

    def __init__(self, config):
        """Initialise the scanner."""

        _LOGGER.info("Initialising BT Home Hub 5")
        self.host = config[CONF_HOST]
        self.last_results = {}

        # Test the router is accessible
        data = bthomehub5_devicelist.get_devicelist(self.host)
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self.update_info()

        return (device for device in self.last_results)

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        if device not in self.last_results:
            self.update_info()

            if not self.last_results:
                return None

        return self.last_results.get(device)

    def update_info(self):
        """Ensure the information from the BT Home Hub 5 is up to date."""

        _LOGGER.info("Scanning")

        data = bthomehub5_devicelist.get_devicelist(self.host)

        if not data:
            _LOGGER.warning("Error scanning devices")
            return

        self.last_results = data
