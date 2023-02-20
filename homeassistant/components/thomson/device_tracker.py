"""Support for THOMSON routers."""
from __future__ import annotations

import logging
import re
import telnetlib

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

_DEVICES_REGEX = re.compile(
    r"(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))\s"
    r"(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s+"
    r"(?P<status>([^\s]+))\s+"
    r"(?P<type>([^\s]+))\s+"
    r"(?P<intf>([^\s]+))\s+"
    r"(?P<hwintf>([^\s]+))\s+"
    r"(?P<host>([^\s]+))"
)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> ThomsonDeviceScanner | None:
    """Validate the configuration and return a THOMSON scanner."""
    scanner = ThomsonDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class ThomsonDeviceScanner(DeviceScanner):
    """This class queries a router running THOMSON firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.last_results = {}

        # Test the router is accessible.
        data = self.get_thomson_data()
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
                return client["host"]
        return None

    def _update_info(self):
        """Ensure the information from the THOMSON router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Checking ARP")
        if not (data := self.get_thomson_data()):
            return False

        # Flag C stands for CONNECTED
        active_clients = [
            client for client in data.values() if client["status"].find("C") != -1
        ]
        self.last_results = active_clients
        return True

    def get_thomson_data(self):
        """Retrieve data from THOMSON and return parsed result."""
        try:
            telnet = telnetlib.Telnet(self.host)
            telnet.read_until(b"Username : ")
            telnet.write((self.username + "\r\n").encode("ascii"))
            telnet.read_until(b"Password : ")
            telnet.write((self.password + "\r\n").encode("ascii"))
            telnet.read_until(b"=>")
            telnet.write(b"hostmgr list\r\n")
            devices_result = telnet.read_until(b"=>").split(b"\r\n")
            telnet.write(b"exit\r\n")
        except EOFError:
            _LOGGER.exception("Unexpected response from router")
            return
        except ConnectionRefusedError:
            _LOGGER.exception("Connection refused by router. Telnet enabled?")
            return

        devices = {}
        for device in devices_result:
            if match := _DEVICES_REGEX.search(device.decode("utf-8")):
                devices[match.group("ip")] = {
                    "ip": match.group("ip"),
                    "mac": match.group("mac").upper(),
                    "host": match.group("host"),
                    "status": match.group("status"),
                }
        return devices
