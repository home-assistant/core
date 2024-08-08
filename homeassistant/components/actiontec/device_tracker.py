"""Support for Actiontec MI424WR (Verizon FIOS) routers."""

from __future__ import annotations

import logging
import telnetlib  # pylint: disable=deprecated-module
from typing import Final

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import LEASES_REGEX
from .model import Device

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> ActiontecDeviceScanner | None:
    """Validate the configuration and return an Actiontec scanner."""
    scanner = ActiontecDeviceScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


class ActiontecDeviceScanner(DeviceScanner):
    """Class which queries an actiontec router for connected devices."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the scanner."""
        self.host: str = config[CONF_HOST]
        self.username: str = config[CONF_USERNAME]
        self.password: str = config[CONF_PASSWORD]
        self.last_results: list[Device] = []
        data = self.get_actiontec_data()
        self.success_init = data is not None
        _LOGGER.info("Scanner initialized")

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client.mac_address for client in self.last_results]

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        for client in self.last_results:
            if client.mac_address == device:
                return client.ip_address
        return None

    def _update_info(self) -> bool:
        """Ensure the information from the router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Scanning")
        if not self.success_init:
            return False

        if (actiontec_data := self.get_actiontec_data()) is None:
            return False
        self.last_results = [
            device for device in actiontec_data if device.timevalid > -60
        ]
        _LOGGER.info("Scan successful")
        return True

    def get_actiontec_data(self) -> list[Device] | None:
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
            return None
        except ConnectionRefusedError:
            _LOGGER.exception("Connection refused by router. Telnet enabled?")
            return None

        devices: list[Device] = []
        for lease in leases_result:
            match = LEASES_REGEX.search(lease.decode("utf-8"))
            if match is not None:
                devices.append(
                    Device(
                        match.group("ip"),
                        match.group("mac").upper(),
                        int(match.group("timevalid")),
                    )
                )
        return devices
