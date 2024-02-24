"""Support for Arris TG2492LG router."""
from __future__ import annotations

from arris_tg2492lg import ConnectBox, Device
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DEFAULT_HOST = "192.168.178.1"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> ArrisDeviceScanner:
    """Return the Arris device scanner."""
    conf = config[DOMAIN]
    url = f"http://{conf[CONF_HOST]}"
    connect_box = ConnectBox(url, conf[CONF_PASSWORD])
    return ArrisDeviceScanner(connect_box)


class ArrisDeviceScanner(DeviceScanner):
    """Class which queries a Arris TG2492LG router for connected devices."""

    def __init__(self, connect_box: ConnectBox) -> None:
        """Initialize the scanner."""
        self.connect_box = connect_box
        self.last_results: list[Device] = []

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results if device.mac]

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        name = next(
            (result.hostname for result in self.last_results if result.mac == device),
            None,
        )
        return name

    def _update_info(self) -> None:
        """Ensure the information from the Arris TG2492LG router is up to date."""
        result = self.connect_box.get_connected_devices()

        last_results: list[Device] = []
        mac_addresses: set[str | None] = set()

        for device in result:
            if device.online and device.mac not in mac_addresses:
                last_results.append(device)
                mac_addresses.add(device.mac)

        self.last_results = last_results
