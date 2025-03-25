"""Support for BT Smart Hub (Sometimes referred to as BT Home Hub 6)."""

from __future__ import annotations

from collections import namedtuple
import logging

from btsmarthub_devicelist import BTSmartHub
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_IP = "192.168.1.254"
CONF_SMARTHUB_MODEL = "smarthub_model"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): cv.string,
        vol.Optional(CONF_SMARTHUB_MODEL): vol.In([1, 2]),
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> BTSmartHubScanner | None:
    """Return a BT Smart Hub scanner if successful."""
    info = config[DEVICE_TRACKER_DOMAIN]
    smarthub_client = BTSmartHub(
        router_ip=info[CONF_HOST], smarthub_model=info.get(CONF_SMARTHUB_MODEL)
    )
    scanner = BTSmartHubScanner(smarthub_client)
    return scanner if scanner.success_init else None


def _create_device(data):
    """Create new device from the dict."""
    ip_address = data.get("IPAddress")
    mac = data.get("PhysAddress")
    host = data.get("UserHostName")
    status = data.get("Active")
    name = data.get("name")
    return _Device(ip_address, mac, host, status, name)


_Device = namedtuple("_Device", ["ip_address", "mac", "host", "status", "name"])  # noqa: PYI024


class BTSmartHubScanner(DeviceScanner):
    """Class which queries a BT Smart Hub."""

    def __init__(self, smarthub_client):
        """Initialise the scanner."""
        self.smarthub = smarthub_client
        self.last_results = []
        self.success_init = False

        # Test the router is accessible
        if self.get_bt_smarthub_data():
            self.success_init = True
        else:
            _LOGGER.warning("Failed to connect to %s", self.smarthub.router_ip)

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for result_device in self.last_results:
            if result_device.mac == device:
                return result_device.name or result_device.host
        return None

    def _update_info(self):
        """Ensure the information from the BT Smart Hub is up to date."""
        if not self.success_init:
            return

        _LOGGER.debug("Scanning")
        if not (data := self.get_bt_smarthub_data()):
            _LOGGER.warning("Error scanning devices")
            return
        self.last_results = data

    def get_bt_smarthub_data(self):
        """Retrieve data from BT Smart Hub and return parsed result."""
        # Request data from bt smarthub into a list of dicts.
        data = self.smarthub.get_devicelist(only_active_devices=True)
        return [_create_device(d) for d in data if d.get("PhysAddress")]
