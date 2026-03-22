"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import binascii
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
    bulk_walk_cmd,
    is_end_of_mib,
)
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST
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

from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    SNMP_VERSIONS,
)
from .util import RequestArgsType, async_create_request_cmd_args

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)

SIGNAL_SNMP_UPDATE = "snmp_update"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BASEOID): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Inclusive(CONF_AUTH_KEY, "keys"): cv.string,
        vol.Inclusive(CONF_PRIV_KEY, "keys"): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SNMP device tracker platform."""
    scanner = SnmpData(hass, config)

    success = await scanner.async_init()
    if not success:
        raise PlatformNotReady("Unable to connect to SNMP host")

    tracked: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add new entities for newly discovered devices."""
        new_entities: list[SnmpDeviceEntity] = []
        for mac in scanner.devices:
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(SnmpDeviceEntity(scanner, mac))
        if new_entities:
            async_add_entities(new_entities)

    async def _async_update(_now: Any = None) -> None:
        """Periodically update device data."""
        await scanner.async_update()
        _async_add_new_entities()
        async_dispatcher_send(hass, SIGNAL_SNMP_UPDATE)

    _async_add_new_entities()
    async_track_time_interval(hass, _async_update, SCAN_INTERVAL)


class SnmpData:
    """Handle communication with SNMP-capable access points."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize the SNMP data handler."""
        self._hass = hass

        community = config[CONF_COMMUNITY]
        self._baseoid = config[CONF_BASEOID]
        self._host = config[CONF_HOST]
        authkey = config.get(CONF_AUTH_KEY)
        authproto = DEFAULT_AUTH_PROTOCOL
        privkey = config.get(CONF_PRIV_KEY)
        privproto = DEFAULT_PRIV_PROTOCOL

        if authkey is not None or privkey is not None:
            if not authkey:
                authproto = "none"
            if not privkey:
                privproto = "none"

            self._auth_data: UsmUserData | CommunityData = UsmUserData(
                community,
                authKey=authkey or None,
                privKey=privkey or None,
                authProtocol=authproto,
                privProtocol=privproto,
            )
        else:
            self._auth_data = CommunityData(
                community, mpModel=SNMP_VERSIONS[DEFAULT_VERSION]
            )

        self._target: UdpTransportTarget | Udp6TransportTarget | None = None
        self._request_args: RequestArgsType | None = None
        self.connected_macs: set[str] = set()
        self.devices: dict[str, dict[str, str | None]] = {}

    async def async_init(self) -> bool:
        """Initialize the SNMP target and test connectivity."""
        try:
            target = await UdpTransportTarget.create(
                (self._host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
            )
        except PySnmpError:
            try:
                target = Udp6TransportTarget(
                    (self._host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
                )
            except PySnmpError as err:
                _LOGGER.error("Invalid SNMP host: %s", err)
                return False

        self._target = target
        self._request_args = await async_create_request_cmd_args(
            self._hass,
            self._auth_data,
            self._target,
            self._baseoid,
        )
        data = await self._async_get_snmp_data()
        return data is not None

    async def async_update(self) -> bool:
        """Fetch latest data from the SNMP device."""
        if not (data := await self._async_get_snmp_data()):
            return False

        self.connected_macs = set()
        self.devices = {}
        for entry in data:
            mac = entry["mac"]
            self.connected_macs.add(mac)
            self.devices[mac] = {"mac": mac}

        return True

    async def _async_get_snmp_data(self) -> list[dict[str, str]] | None:
        """Fetch MAC addresses from access point via SNMP."""
        devices: list[dict[str, str]] = []
        if TYPE_CHECKING:
            assert self._request_args is not None

        engine, auth_data, target, context_data, object_type = self._request_args
        walker = bulk_walk_cmd(
            engine,
            auth_data,
            target,
            context_data,
            0,
            50,
            object_type,
            lexicographicMode=False,
        )
        async for errindication, errstatus, errindex, res in walker:
            if errindication:
                _LOGGER.error("SNMPLIB error: %s", errindication)
                return None
            if errstatus:
                _LOGGER.error(
                    "SNMP error: %s at %s",
                    errstatus.prettyPrint(),
                    (errindex and res[int(errindex) - 1][0]) or "?",
                )
                return None

            for _oid, value in res:
                if not is_end_of_mib(res):
                    try:
                        mac = binascii.hexlify(value.asOctets()).decode("utf-8")
                    except AttributeError:
                        continue
                    _LOGGER.debug("Found MAC address: %s", mac)
                    mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
                    devices.append({"mac": mac})
        return devices


class SnmpDeviceEntity(ScannerEntity):
    """Representation of a device discovered via SNMP."""

    _attr_should_poll = False

    def __init__(self, scanner: SnmpData, mac: str) -> None:
        """Initialize the entity."""
        self._scanner = scanner
        self._mac = mac
        self._attr_name = mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._mac in self._scanner.connected_macs

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
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
                SIGNAL_SNMP_UPDATE,
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Handle updated data from the scanner."""
        self.async_write_ha_state()
