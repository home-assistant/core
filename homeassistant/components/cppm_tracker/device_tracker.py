"""Support for ClearPass Policy Manager."""

from __future__ import annotations

from datetime import timedelta
import logging

from clearpasspy import ClearPass
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

SCAN_INTERVAL = timedelta(seconds=120)

GRANT_TYPE = "client_credentials"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> CPPMDeviceScanner | None:
    """Initialize Scanner."""

    config = config[DEVICE_TRACKER_DOMAIN]

    data = {
        "server": config[CONF_HOST],
        "grant_type": GRANT_TYPE,
        "secret": config[CONF_API_KEY],
        "client": config[CONF_CLIENT_ID],
    }
    cppm = ClearPass(data)
    if cppm.access_token is None:
        return None
    _LOGGER.debug("Successfully received Access Token")
    return CPPMDeviceScanner(cppm)


class CPPMDeviceScanner(DeviceScanner):
    """Initialize class."""

    def __init__(self, cppm):
        """Initialize class."""
        self._cppm = cppm
        self.results = None

    def scan_devices(self):
        """Initialize scanner."""
        self.get_cppm_data()
        return [device["mac"] for device in self.results]

    def get_device_name(self, device):
        """Retrieve device name."""
        return next(
            (result["name"] for result in self.results if result["mac"] == device), None
        )

    def get_cppm_data(self):
        """Retrieve data from Aruba Clearpass and return parsed result."""
        endpoints = self._cppm.get_endpoints(100)["_embedded"]["items"]
        devices = []
        for item in endpoints:
            if self._cppm.online_status(item["mac_address"]):
                device = {"mac": item["mac_address"], "name": item["mac_address"]}
                devices.append(device)
            else:
                continue
        _LOGGER.debug("Devices: %s", devices)
        self.results = devices
