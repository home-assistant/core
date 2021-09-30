"""Support for Aruba Access Points."""
import logging
import re

import pexpect
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_DEVICES_REGEX = re.compile(
    r"(?P<name>([^\s]+)?)\s+"
    + r"(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s+"
    + r"(?P<mac>([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))\s+"
)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return a Aruba scanner."""
    scanner = ArubaDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class ArubaDeviceScanner(DeviceScanner):
    """This class queries a Aruba Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.last_results = {}

        # Test the router is accessible.
        data = self.get_aruba_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client["mac"] == device:
                return client["name"]
        return None

    def _update_info(self):
        """Ensure the information from the Aruba Access Point is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        data = self.get_aruba_data()
        if not data:
            return False

        self.last_results = data.values()
        return True

    def get_aruba_data(self):
        """Retrieve data from Aruba Access Point and return parsed result."""

        connect = f"ssh {self.username}@{self.host}"
        ssh = pexpect.spawn(connect)
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
            return
        if query == 2:
            _LOGGER.error("Unexpected response from router")
            return
        if query == 3:
            ssh.sendline("yes")
            ssh.expect("password:")
        elif query == 4:
            _LOGGER.error("Host key changed")
            return
        elif query == 5:
            _LOGGER.error("Connection refused by server")
            return
        elif query == 6:
            _LOGGER.error("Connection timed out")
            return
        ssh.sendline(self.password)
        ssh.expect("#")
        ssh.sendline("show clients")
        ssh.expect("#")
        devices_result = ssh.before.split(b"\r\n")
        ssh.sendline("exit")

        devices = {}
        for device in devices_result:
            match = _DEVICES_REGEX.search(device.decode("utf-8"))
            if match:
                devices[match.group("ip")] = {
                    "ip": match.group("ip"),
                    "mac": match.group("mac").upper(),
                    "name": match.group("name"),
                }
        return devices
