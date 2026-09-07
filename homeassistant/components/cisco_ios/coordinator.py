"""DataUpdateCoordinator for Cisco IOS."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from pexpect import pxssh

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    CONF_TRACK_NEW,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type CiscoIOSConfigEntry = ConfigEntry[CiscoIOSDataUpdateCoordinator]


@dataclass
class CiscoIOSDevice:
    """Device seen in the ARP table of the router."""

    ip_address: str
    last_seen: datetime
    connected: bool


def _parse_cisco_mac_address(cisco_hardware_addr: str) -> str:
    """Parse a Cisco formatted HW address to normal MAC.

    For example, convert 001d.ec02.07ab to 00:1D:EC:02:07:AB.
    """
    cisco_hardware_addr = cisco_hardware_addr.replace(".", "")
    blocks = [
        cisco_hardware_addr[x : x + 2] for x in range(0, len(cisco_hardware_addr), 2)
    ]

    return ":".join(blocks).upper()


class CiscoIOSArpScanner:
    """Fetch connected devices from a router running Cisco IOS."""

    def __init__(
        self, host: str, username: str, password: str, port: int | None
    ) -> None:
        """Initialize the scanner."""
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def get_devices(self) -> dict[str, str]:
        """Return the connected devices as a mapping of MAC address to IP address.

        Raises pxssh.ExceptionPxssh if the router cannot be reached.
        """
        devices: dict[str, str] = {}

        # Remove the first two lines, as they contain the arp command
        # and the arp table titles e.g.
        # show ip arp
        # Protocol  Address | Age (min) | Hardware Addr | Type | Interface
        for line in self._get_arp_data().splitlines()[2:]:
            parts = line.split()
            if len(parts) != 6:
                continue

            # ['Internet', '10.10.11.1', '-', '0027.d32d.0123', 'ARPA',
            # 'GigabitEthernet0']
            age = parts[2]
            if age != "-" and int(age) < 1:
                devices[_parse_cisco_mac_address(parts[3])] = parts[1]

        return devices

    def _get_arp_data(self) -> str:
        """Open a connection to the router and get the arp entries."""
        cisco_ssh: pxssh.pxssh[str] = pxssh.pxssh(encoding="utf-8")
        cisco_ssh.login(
            self.host,
            self.username,
            self.password,
            port=self.port,
            auto_prompt_reset=False,
        )

        # Find the hostname
        initial_line = (cisco_ssh.before or "").splitlines()
        router_hostname = initial_line[len(initial_line) - 1]
        router_hostname += "#"
        # Set the discovered hostname as prompt
        cisco_ssh.PROMPT = f"(?i)^{router_hostname}"
        # Allow full arp table to print at once
        cisco_ssh.sendline("terminal length 0")
        if not cisco_ssh.prompt(1):
            raise pxssh.ExceptionPxssh("Timed out waiting for the router prompt")

        cisco_ssh.sendline("show ip arp")
        if not cisco_ssh.prompt(1):
            raise pxssh.ExceptionPxssh("Timed out waiting for the arp table")

        return cisco_ssh.before or ""


class CiscoIOSDataUpdateCoordinator(DataUpdateCoordinator[dict[str, CiscoIOSDevice]]):
    """Class to manage fetching data from the Cisco IOS router."""

    config_entry: CiscoIOSConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: CiscoIOSConfigEntry) -> None:
        """Initialize the coordinator using the config entry."""
        self.host = config_entry.data[CONF_HOST]
        self.scanner = CiscoIOSArpScanner(
            host=self.host,
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            port=config_entry.data.get(CONF_PORT),
        )
        self.consider_home = timedelta(
            seconds=config_entry.options.get(
                CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
            )
        )
        # Imported YAML entries carry the legacy track_new_devices setting,
        # entries created through the UI keep the ScannerEntity default of
        # not enabling newly discovered devices.
        self.track_new = config_entry.options.get(CONF_TRACK_NEW, False)
        self._devices: dict[str, CiscoIOSDevice] = {}

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, CiscoIOSDevice]:
        """Fetch the connected devices from the router."""
        try:
            connected = await self.hass.async_add_executor_job(self.scanner.get_devices)
        except pxssh.ExceptionPxssh as err:
            raise UpdateFailed(
                f"Failed to fetch data from Cisco IOS router {self.host}"
            ) from err

        now = dt_util.utcnow()
        for mac, ip_address in connected.items():
            self._devices[mac] = CiscoIOSDevice(
                ip_address=ip_address, last_seen=now, connected=True
            )
        # A device absent from the current scan stays connected until the
        # consider_home grace period has elapsed since it was last seen.
        for mac, device in self._devices.items():
            if mac not in connected:
                device.connected = now - device.last_seen <= self.consider_home
        return dict(self._devices)
