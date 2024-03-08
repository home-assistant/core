"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import binascii
import logging

from pysnmp.error import PySnmpError
import pysnmp.hlapi.asyncio as hlapi
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
    bulkWalkCmd,
    isEndOfMib,
)
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
    CONF_VERSION,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BASEOID): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.In(SNMP_VERSIONS),
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_AUTH_KEY): cv.string,
        vol.Optional(CONF_AUTH_PROTOCOL, default=DEFAULT_AUTH_PROTOCOL): vol.In(
            MAP_AUTH_PROTOCOLS
        ),
        vol.Optional(CONF_PRIV_KEY): cv.string,
        vol.Optional(CONF_PRIV_PROTOCOL, default=DEFAULT_PRIV_PROTOCOL): vol.In(
            MAP_PRIV_PROTOCOLS
        ),
    }
)


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> SnmpScanner | None:
    """Validate the configuration and return an SNMP scanner."""
    scanner = SnmpScanner(config[DOMAIN])
    await scanner.test_device_readable()

    return scanner if scanner.success_init else None


class SnmpScanner(DeviceScanner):
    """Queries any SNMP capable Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner and test the target device."""
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        community = config.get(CONF_COMMUNITY)
        baseoid = config.get(CONF_BASEOID)
        version = config[CONF_VERSION]
        username = config.get(CONF_USERNAME)
        authkey = config.get(CONF_AUTH_KEY)
        authproto = config[CONF_AUTH_PROTOCOL]
        privkey = config.get(CONF_PRIV_KEY)
        privproto = config[CONF_PRIV_PROTOCOL]

        try:
            # Try IPv4 first.
            target = UdpTransportTarget((host, port), timeout=DEFAULT_TIMEOUT)
        except PySnmpError:
            # Then try IPv6.
            try:
                target = Udp6TransportTarget((host, port), timeout=DEFAULT_TIMEOUT)
            except PySnmpError as err:
                _LOGGER.error("Invalid SNMP host: %s", err)
                return

        if version == "3":
            if not authkey:
                authproto = "none"
            if not privkey:
                privproto = "none"

            request_args = [
                SnmpEngine(),
                UsmUserData(
                    username,
                    authKey=authkey or None,
                    privKey=privkey or None,
                    authProtocol=getattr(hlapi, MAP_AUTH_PROTOCOLS[authproto]),
                    privProtocol=getattr(hlapi, MAP_PRIV_PROTOCOLS[privproto]),
                ),
                target,
                ContextData(),
            ]
        else:
            request_args = [
                SnmpEngine(),
                CommunityData(community, mpModel=SNMP_VERSIONS[version]),
                target,
                ContextData(),
            ]

        self.request_args = request_args
        self.baseoid = baseoid
        self.last_results = []
        self.success_init = False

    async def test_device_readable(self):
        """Make a one-off read to check if the target device is reachable and readable."""
        data = await self.get_snmp_data()
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._async_update_info()
        return [client["mac"] for client in self.last_results if client.get("mac")]

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # We have no names
        return None

    async def _async_update_info(self):
        """Ensure the information from the device is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        if not (data := await self.get_snmp_data()):
            return False

        self.last_results = data
        return True

    async def get_snmp_data(self):
        """Fetch MAC addresses from access point via SNMP."""
        devices = []

        walker = bulkWalkCmd(
            *self.request_args,
            0,
            50,
            ObjectType(ObjectIdentity(self.baseoid)),
            lexicographicMode=False,
        )
        async for errindication, errstatus, errindex, res in walker:
            if errindication:
                _LOGGER.error("SNMPLIB error: %s", errindication)
                return
            if errstatus:
                _LOGGER.error(
                    "SNMP error: %s at %s",
                    errstatus.prettyPrint(),
                    errindex and res[int(errindex) - 1][0] or "?",
                )
                return

            for _, val in res:  # oid, value
                if not isEndOfMib(res):
                    try:
                        mac = binascii.hexlify(val.asOctets()).decode("utf-8")
                    except AttributeError:
                        continue
                    _LOGGER.debug("Found MAC address: %s", mac)
                    mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
                    devices.append({"mac": mac})
        return devices
