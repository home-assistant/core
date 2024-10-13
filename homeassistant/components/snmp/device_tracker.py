"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import binascii
import logging
from typing import TYPE_CHECKING

from pysnmp.error import PySnmpError
from pysnmp.hlapi.asyncio import (
    CommunityData,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
    bulkWalkCmd,
    isEndOfMib,
)
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

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

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BASEOID): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Inclusive(CONF_AUTH_KEY, "keys"): cv.string,
        vol.Inclusive(CONF_PRIV_KEY, "keys"): cv.string,
    }
)


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> SnmpScanner | None:
    """Validate the configuration and return an SNMP scanner."""
    scanner = SnmpScanner(config[DEVICE_TRACKER_DOMAIN])
    await scanner.async_init(hass)

    return scanner if scanner.success_init else None


class SnmpScanner(DeviceScanner):
    """Queries any SNMP capable Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner and test the target device."""
        host = config[CONF_HOST]
        community = config[CONF_COMMUNITY]
        baseoid = config[CONF_BASEOID]
        authkey = config.get(CONF_AUTH_KEY)
        authproto = DEFAULT_AUTH_PROTOCOL
        privkey = config.get(CONF_PRIV_KEY)
        privproto = DEFAULT_PRIV_PROTOCOL

        try:
            # Try IPv4 first.
            target = UdpTransportTarget((host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT)
        except PySnmpError:
            # Then try IPv6.
            try:
                target = Udp6TransportTarget(
                    (host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
                )
            except PySnmpError as err:
                _LOGGER.error("Invalid SNMP host: %s", err)
                return

        if authkey is not None or privkey is not None:
            if not authkey:
                authproto = "none"
            if not privkey:
                privproto = "none"

            self._auth_data = UsmUserData(
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

        self._target = target
        self.request_args: RequestArgsType | None = None
        self.baseoid = baseoid
        self.last_results = []
        self.success_init = False

    async def async_init(self, hass: HomeAssistant) -> None:
        """Make a one-off read to check if the target device is reachable and readable."""
        self.request_args = await async_create_request_cmd_args(
            hass, self._auth_data, self._target, self.baseoid
        )
        data = await self.async_get_snmp_data()
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._async_update_info()
        return [client["mac"] for client in self.last_results if client.get("mac")]

    async def async_get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        # We have no names
        return None

    async def _async_update_info(self):
        """Ensure the information from the device is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        if not (data := await self.async_get_snmp_data()):
            return False

        self.last_results = data
        return True

    async def async_get_snmp_data(self):
        """Fetch MAC addresses from access point via SNMP."""
        devices = []
        if TYPE_CHECKING:
            assert self.request_args is not None

        engine, auth_data, target, context_data, object_type = self.request_args
        walker = bulkWalkCmd(
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
                    errindex and res[int(errindex) - 1][0] or "?",
                )
                return None

            for _oid, value in res:
                if not isEndOfMib(res):
                    try:
                        mac = binascii.hexlify(value.asOctets()).decode("utf-8")
                    except AttributeError:
                        continue
                    _LOGGER.debug("Found MAC address: %s", mac)
                    mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
                    devices.append({"mac": mac})
        return devices
