"""Support for THOMSON routers."""

from __future__ import annotations

from datetime import timedelta
import logging
import re
import telnetlib  # pylint: disable=deprecated-module
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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

SCAN_INTERVAL = timedelta(seconds=12)

SIGNAL_THOMSON_UPDATE = "thomson_update"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Thomson device tracker platform."""
    scanner = ThomsonData(config)

    success = await hass.async_add_executor_job(scanner.update)
    if not success:
        raise PlatformNotReady("Unable to connect to Thomson router")

    tracked: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add new entities for newly discovered devices."""
        new_entities: list[ThomsonDeviceEntity] = []
        for mac in scanner.devices:
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(ThomsonDeviceEntity(scanner, mac))
        if new_entities:
            async_add_entities(new_entities)

    async def _async_update(_now: Any = None) -> None:
        """Periodically update device data."""
        await hass.async_add_executor_job(scanner.update)
        _async_add_new_entities()
        async_dispatcher_send(hass, SIGNAL_THOMSON_UPDATE)

    _async_add_new_entities()
    async_track_time_interval(hass, _async_update, SCAN_INTERVAL)


class ThomsonData:
    """Handle communication with the Thomson router."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the data handler."""
        self._host: str = config[CONF_HOST]
        self._username: str = config[CONF_USERNAME]
        self._password: str = config[CONF_PASSWORD]
        self.connected_macs: set[str] = set()
        self.devices: dict[str, dict[str, str | None]] = {}

    def update(self) -> bool:
        """Fetch data from the Thomson router.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("Checking ARP")

        data = self._get_thomson_data()
        if not data:
            return False

        connected_macs: set[str] = set()
        devices: dict[str, dict[str, str | None]] = {}

        for client in data.values():
            mac = client["mac"]
            devices[mac] = {
                "hostname": client["host"],
                "ip": client["ip"],
            }
            # Flag C stands for CONNECTED
            if "C" in client["status"]:
                connected_macs.add(mac)

        self.connected_macs = connected_macs
        self.devices = devices
        return True

    def _get_thomson_data(self) -> dict[str, dict[str, str]] | None:
        """Retrieve data from Thomson and return parsed result."""
        try:
            telnet = telnetlib.Telnet(self._host)
            telnet.read_until(b"Username : ")
            telnet.write((self._username + "\r\n").encode("ascii"))
            telnet.read_until(b"Password : ")
            telnet.write((self._password + "\r\n").encode("ascii"))
            telnet.read_until(b"=>")
            telnet.write(b"hostmgr list\r\n")
            devices_result = telnet.read_until(b"=>").split(b"\r\n")
            telnet.write(b"exit\r\n")
        except EOFError:
            _LOGGER.exception("Unexpected response from router")
            return None
        except ConnectionRefusedError:
            _LOGGER.exception("Connection refused by router. Telnet enabled?")
            return None

        devices: dict[str, dict[str, str]] = {}
        for device in devices_result:
            if match := _DEVICES_REGEX.search(device.decode("utf-8")):
                devices[match.group("ip")] = {
                    "ip": match.group("ip"),
                    "mac": match.group("mac").upper(),
                    "host": match.group("host"),
                    "status": match.group("status"),
                }
        return devices


class ThomsonDeviceEntity(ScannerEntity):
    """Representation of a device connected to a Thomson router."""

    _attr_should_poll = False

    def __init__(self, scanner: ThomsonData, mac: str) -> None:
        """Initialize the entity."""
        self._scanner = scanner
        self._mac = mac
        device = scanner.devices.get(mac, {})
        self._attr_name: str | None = device.get("hostname") or mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._mac in self._scanner.connected_macs

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        if device := self._scanner.devices.get(self._mac):
            return device.get("hostname")
        return None

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        if device := self._scanner.devices.get(self._mac):
            return device.get("ip")
        return None

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_THOMSON_UPDATE,
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Handle updated data from the scanner."""
        self.async_write_ha_state()
