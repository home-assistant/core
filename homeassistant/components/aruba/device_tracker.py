"""Support for Aruba Access Points."""

from __future__ import annotations

import logging
import re
from typing import Any

import pexpect
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

_DEVICES_REGEX = re.compile(
    r"(?P<name>([^\s]+)?)\s+"
    r"(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s+"
    r"(?P<mac>([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))\s+"
)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> ArubaDeviceScanner | None:
    """Validate the configuration and return a Aruba scanner."""
    scanner = ArubaDeviceScanner(config[DEVICE_TRACKER_DOMAIN])

    return scanner if scanner.success_init else None


class ArubaDeviceScanner(DeviceScanner):
    """Class which queries a Aruba Access Point for connected devices."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the scanner."""
        self.host: str = config[CONF_HOST]
        self.username: str = config[CONF_USERNAME]
        self.password: str = config[CONF_PASSWORD]

        self.last_results: dict[str, dict[str, str]] = {}

        # Test the router is accessible.
        data = self.get_aruba_data()
        self.success_init = data is not None

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.last_results.values()]

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results.values():
            if client["mac"] == device:
                return client["name"]
        return None

    def _update_info(self) -> bool:
        """Ensure the information from the Aruba Access Point is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        if not (data := self.get_aruba_data()):
            return False

        self.last_results = data
        return True

    def get_aruba_data(self) -> dict[str, dict[str, str]] | None:
        """Retrieve data from Aruba Access Point and return parsed result."""

        connect = f"ssh {self.username}@{self.host} -o HostKeyAlgorithms=ssh-rsa"
        ssh: pexpect.spawn[str] = pexpect.spawn(connect, encoding="utf-8")
        query = ssh.expect(
            [
                "password:",
                pexpect.TIMEOUT,
                pexpect.EOF,
                "continue connecting (yes/no)?",
                "Host key verification failed.",
                "Connection refused",
                "Connection timed out",
            ],
            timeout=120,
        )
        if query == 1:
            _LOGGER.error("Timeout")
            return None
        if query == 2:
            _LOGGER.error("Unexpected response from router")
            return None
        if query == 3:
            ssh.sendline("yes")
            ssh.expect("password:")
        elif query == 4:
            _LOGGER.error("Host key changed")
            return None
        elif query == 5:
            _LOGGER.error("Connection refused by server")
            return None
        elif query == 6:
            _LOGGER.error("Connection timed out")
            return None
        ssh.sendline(self.password)
        ssh.expect("#")
        ssh.sendline("show clients")
        ssh.expect("#")
        devices_result = (ssh.before or "").splitlines()
        ssh.sendline("exit")

        devices: dict[str, dict[str, str]] = {}
        for device in devices_result:
            if match := _DEVICES_REGEX.search(device):
                devices[match.group("ip")] = {
                    "ip": match.group("ip"),
                    "mac": match.group("mac").upper(),
                    "name": match.group("name"),
                }
        return devices
