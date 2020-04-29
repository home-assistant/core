"""Support for Arris TG2492LG router."""
import logging
from typing import List

from arris_tg2492lg import ConnectBox, Device
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "192.168.178.1"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    }
)


def get_scanner(hass, config):
    """Return the Arris device scanner."""
    conf = config[DOMAIN]
    url = f"http://{conf[CONF_HOST]}"
    connect_box = ConnectBox(url, conf[CONF_PASSWORD])
    return ArrisDeviceScanner(connect_box)


class ArrisDeviceScanner(DeviceScanner):
    """This class queries a Arris TG2492LG router for connected devices."""

    def __init__(self, connect_box: ConnectBox):
        """Initialize the scanner."""
        self.connect_box = connect_box
        self.last_results: List[Device] = []

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        name = next(
            (result.hostname for result in self.last_results if result.mac == device),
            None,
        )
        return name

    def _update_info(self):
        """Ensure the information from the Arris TG2492LG router is up to date."""
        result = self.connect_box.get_connected_devices()

        last_results = []
        mac_addresses = set()

        for device in result:
            if device.online and device.mac not in mac_addresses:
                last_results.append(device)
                mac_addresses.add(device.mac)

        self.last_results = last_results
