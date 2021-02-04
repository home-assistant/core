"""Support for Actiontec MI424WR (Verizon FIOS) routers."""
from collections import namedtuple
import logging
import re
import telnetlib

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

_LEASES_REGEX = re.compile(
    r"(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})"
    + r"\smac:\s(?P<mac>([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))"
    + r"\svalid\sfor:\s(?P<timevalid>(-?\d+))"
    + r"\ssec"
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return an Actiontec scanner."""
    scanner = ActiontecDeviceScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["mac", "ip", "last_update"])


class ActiontecDeviceScanner(DeviceScanner):
    """This class queries an actiontec router for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.last_results = []
        data = self.get_actiontec_data()
        self.success_init = data is not None
        _LOGGER.info("canner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client.mac for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client.mac == device:
                return client.ip
        return None

    def _update_info(self):
        """Ensure the information from the router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Scanning")
        if not self.success_init:
            return False

        now = dt_util.now()
        actiontec_data = self.get_actiontec_data()
        if not actiontec_data:
            return False
        self.last_results = [
            Device(data["mac"], name, now)
            for name, data in actiontec_data.items()
            if data["timevalid"] > -60
        ]
        _LOGGER.info("Scan successful")
        return True

    def get_actiontec_data(self):
        """Retrieve data from Actiontec MI424WR and return parsed result."""
        try:
            telnet = telnetlib.Telnet(self.host)
            telnet.read_until(b"Username: ")
            telnet.write((f"{self.username}\n").encode("ascii"))
            telnet.read_until(b"Password: ")
            telnet.write((f"{self.password}\n").encode("ascii"))
            prompt = telnet.read_until(b"Wireless Broadband Router> ").split(b"\n")[-1]
            telnet.write(b"firewall mac_cache_dump\n")
            telnet.write(b"\n")
            telnet.read_until(prompt)
            leases_result = telnet.read_until(prompt).split(b"\n")[1:-1]
            telnet.write(b"exit\n")
        except EOFError:
            _LOGGER.exception("Unexpected response from router")
            return
        except ConnectionRefusedError:
            _LOGGER.exception("Connection refused by router. Telnet enabled?")
            return None

        devices = {}
        for lease in leases_result:
            match = _LEASES_REGEX.search(lease.decode("utf-8"))
            if match is not None:
                devices[match.group("ip")] = {
                    "ip": match.group("ip"),
                    "mac": match.group("mac").upper(),
                    "timevalid": int(match.group("timevalid")),
                }
        return devices
