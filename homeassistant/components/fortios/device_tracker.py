"""Support to use FortiOS device like FortiGate as device tracker.

This component is part of the device_tracker platform.
"""

from __future__ import annotations

import logging
from typing import Any

from awesomeversion import AwesomeVersion
from fortiosapi import FortiOSAPI
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)
DEFAULT_VERIFY_SSL = False


PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> FortiOSDeviceScanner | None:
    """Validate the configuration and return a FortiOSDeviceScanner."""
    config = config[DEVICE_TRACKER_DOMAIN]

    host = config[CONF_HOST]
    verify_ssl = config[CONF_VERIFY_SSL]
    token = config[CONF_TOKEN]

    fgt = FortiOSAPI()

    try:
        fgt.tokenlogin(host, token, verify_ssl, None, 12, "root")
    except ConnectionError as ex:
        _LOGGER.error("ConnectionError to FortiOS API: %s", ex)
        return None
    except Exception as ex:  # noqa: BLE001
        _LOGGER.error("Failed to login to FortiOS API: %s", ex)
        return None

    status_json = fgt.monitor("system/status", "")

    current_version = AwesomeVersion(status_json["version"])
    minimum_version = AwesomeVersion("6.4.3")
    if current_version < minimum_version:
        _LOGGER.error(
            "Unsupported FortiOS version: %s. Version %s and newer are supported",
            current_version,
            minimum_version,
        )
        return None

    return FortiOSDeviceScanner(fgt)


class FortiOSDeviceScanner(DeviceScanner):
    """Class which queries a FortiOS unit for connected devices."""

    def __init__(self, fgt) -> None:
        """Initialize the scanner."""
        self._clients: list[str] = []
        self._clients_json: dict[str, Any] = {}
        self._fgt = fgt

    def update(self):
        """Update clients from the device."""
        clients_json = self._fgt.monitor(
            "user/device/query",
            "",
            parameters={"filter": "format=master_mac|hostname|is_online"},
        )

        self._clients_json = clients_json

        self._clients = []

        if clients_json:
            try:
                for client in clients_json["results"]:
                    if (
                        "is_online" in client
                        and "master_mac" in client
                        and client["is_online"]
                    ):
                        self._clients.append(client["master_mac"].upper())
            except KeyError as kex:
                _LOGGER.error("Key not found in clients: %s", kex)

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self.update()
        return self._clients

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        _LOGGER.debug("Getting name of device %s", device)

        device = device.lower()

        if (data := self._clients_json) == 0:
            _LOGGER.error("No json results to get device names")
            return None

        for client in data["results"]:
            if "master_mac" in client and client["master_mac"] == device:
                if "hostname" in client:
                    name = client["hostname"]
                else:
                    name = client["master_mac"].replace(":", "_")
                return name
        return None
