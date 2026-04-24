"""Support for Actiontec MI424WR (Verizon FIOS) routers."""

from __future__ import annotations

from datetime import timedelta
import logging
import telnetlib  # pylint: disable=deprecated-module
from typing import Final

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
    SourceType,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import LEASES_REGEX
from .model import Device

_LOGGER: Final = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=120)

SIGNAL_ACTIONTEC_UPDATE: Final = "actiontec_update"

PLATFORM_SCHEMA: Final = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
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
    """Set up the Actiontec device tracker platform."""
    host: str = config[CONF_HOST]
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]

    scanner = ActiontecScanner(hass, host, username, password, async_add_entities)

    data = await hass.async_add_executor_job(scanner.get_actiontec_data)
    if data is None:
        _LOGGER.error("Could not connect to Actiontec router")
        return

    scanner.process_results(data)

    track_time_interval(hass, scanner.update, SCAN_INTERVAL)


class ActiontecScanner:
    """Manage scanning the Actiontec router for connected devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.async_add_entities = async_add_entities
        self.tracked_devices: dict[str, ActiontecDeviceEntity] = {}

    def process_results(self, devices: list[Device]) -> None:
        """Process scan results and add/update entities."""
        active_macs: set[str] = set()
        new_entities: list[ActiontecDeviceEntity] = []

        for device in devices:
            if device.timevalid <= -60:
                continue
            mac = device.mac_address
            active_macs.add(mac)

            if mac not in self.tracked_devices:
                entity = ActiontecDeviceEntity(mac, device.ip_address)
                self.tracked_devices[mac] = entity
                new_entities.append(entity)

        if new_entities:
            self.async_add_entities(new_entities)

        # Update connected state for all tracked devices
        for mac, entity in self.tracked_devices.items():
            entity.set_connected(mac in active_macs)

        dispatcher_send(self.hass, SIGNAL_ACTIONTEC_UPDATE)

    def update(self, now=None) -> None:
        """Update device states from the router."""
        data = self.get_actiontec_data()
        if data is None:
            return
        self.process_results(data)

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


class ActiontecDeviceEntity(ScannerEntity):
    """Representation of a device connected to the Actiontec router."""

    _attr_should_poll = False

    def __init__(self, mac: str, ip_address: str) -> None:
        """Initialize the device entity."""
        self._mac = mac
        self._ip_address = ip_address
        self._connected = True

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected."""
        return self._connected

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return the hostname (IP address used as name)."""
        return self._ip_address

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        return self._ip_address

    def set_connected(self, connected: bool) -> None:
        """Set the connected state."""
        self._connected = connected

    async def async_added_to_hass(self) -> None:
        """Register dispatcher listener."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ACTIONTEC_UPDATE, self._async_update
            )
        )

    @callback
    def _async_update(self) -> None:
        """Update the entity."""
        self.async_write_ha_state()
