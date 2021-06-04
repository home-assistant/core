"""Support for scanning a network with nmap."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from getmac import get_mac_address
from nmap import PortScanner, PortScannerError
import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import CONF_HOME_INTERVAL, CONF_OPTIONS, DEFAULT_OPTIONS
from .model import Device

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final[Schema] = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): cv.ensure_list,
        vol.Required(CONF_HOME_INTERVAL, default=0): cv.positive_int,
        vol.Optional(CONF_EXCLUDE, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_OPTIONS, default=DEFAULT_OPTIONS): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> NmapDeviceScanner:
    """Validate the configuration and return a Nmap scanner."""
    return NmapDeviceScanner(config[DOMAIN])


class NmapDeviceScanner(DeviceScanner):
    """This class scans for devices using nmap."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the scanner."""
        self.last_results: list[Device] = []

        self.hosts: list[str] = config[CONF_HOSTS]
        self.exclude: list[str] = config[CONF_EXCLUDE]
        minutes: int = config[CONF_HOME_INTERVAL]
        self._options: str = config[CONF_OPTIONS]
        self.home_interval = timedelta(minutes=minutes)

        _LOGGER.debug("Scanner initialized")

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        _LOGGER.debug("Nmap last results %s", self.last_results)

        return [device.mac for device in self.last_results]

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result.name for result in self.last_results if result.mac == device
        ]

        if filter_named:
            return filter_named[0]
        return None

    def get_extra_attributes(self, device: str) -> dict[str, str | None]:
        """Return the IP of the given device."""
        filter_ip = next(
            (result.ip for result in self.last_results if result.mac == device), None
        )
        return {"ip": filter_ip}

    def _update_info(self) -> bool:
        """Scan the network for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Scanning")

        scanner = PortScanner()

        options = self._options

        if self.home_interval:
            boundary = dt_util.now() - self.home_interval
            last_results = [
                device for device in self.last_results if device.last_update > boundary
            ]
            if last_results:
                exclude_hosts = self.exclude + [device.ip for device in last_results]
            else:
                exclude_hosts = self.exclude
        else:
            last_results = []
            exclude_hosts = self.exclude
        if exclude_hosts:
            options += f" --exclude {','.join(exclude_hosts)}"

        try:
            result = scanner.scan(hosts=" ".join(self.hosts), arguments=options)
        except PortScannerError:
            return False

        now = dt_util.now()
        for ipv4, info in result["scan"].items():
            if info["status"]["state"] != "up":
                continue
            name = info["hostnames"][0]["name"] if info["hostnames"] else ipv4
            # Mac address only returned if nmap ran as root
            mac = info["addresses"].get("mac") or get_mac_address(ip=ipv4)
            if mac is None:
                _LOGGER.info("No MAC address found for %s", ipv4)
                continue
            last_results.append(Device(mac.upper(), name, ipv4, now))

        self.last_results = last_results

        _LOGGER.debug("nmap scan successful")
        return True
