"""Support for SNMP enabled switch."""

from __future__ import annotations

import logging
from typing import Any

import pysnmp.hlapi.asyncio as hlapi
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ObjectIdentity,
    ObjectType,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    setCmd,
)
from pysnmp.proto.rfc1902 import (
    Counter32,
    Counter64,
    Gauge32,
    Integer,
    Integer32,
    IpAddress,
    Null,
    ObjectIdentifier,
    OctetString,
    Opaque,
    TimeTicks,
    Unsigned32,
)
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
    CONF_VARTYPE,
    CONF_VERSION,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_VARTYPE,
    DEFAULT_VERSION,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
)
from .util import (
    CommandArgsType,
    RequestArgsType,
    async_create_command_cmd_args,
    async_create_request_cmd_args,
)

_LOGGER = logging.getLogger(__name__)

CONF_COMMAND_OID = "command_oid"
CONF_COMMAND_PAYLOAD_OFF = "command_payload_off"
CONF_COMMAND_PAYLOAD_ON = "command_payload_on"

DEFAULT_COMMUNITY = "private"
DEFAULT_PAYLOAD_OFF = 0
DEFAULT_PAYLOAD_ON = 1

MAP_SNMP_VARTYPES = {
    "Counter32": Counter32,
    "Counter64": Counter64,
    "Gauge32": Gauge32,
    "Integer32": Integer32,
    "Integer": Integer,
    "IpAddress": IpAddress,
    "Null": Null,
    # some work todo to support tuple ObjectIdentifier, this just supports str
    "ObjectIdentifier": ObjectIdentifier,
    "OctetString": OctetString,
    "Opaque": Opaque,
    "TimeTicks": TimeTicks,
    "Unsigned32": Unsigned32,
}

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BASEOID): cv.string,
        vol.Optional(CONF_COMMAND_OID): cv.string,
        vol.Optional(CONF_COMMAND_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_COMMAND_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.In(SNMP_VERSIONS),
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_AUTH_KEY): cv.string,
        vol.Optional(CONF_AUTH_PROTOCOL, default=DEFAULT_AUTH_PROTOCOL): vol.In(
            MAP_AUTH_PROTOCOLS
        ),
        vol.Optional(CONF_PRIV_KEY): cv.string,
        vol.Optional(CONF_PRIV_PROTOCOL, default=DEFAULT_PRIV_PROTOCOL): vol.In(
            MAP_PRIV_PROTOCOLS
        ),
        vol.Optional(CONF_VARTYPE, default=DEFAULT_VARTYPE): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SNMP switch."""
    name: str = config[CONF_NAME]
    host: str = config[CONF_HOST]
    port: int = config[CONF_PORT]
    community = config.get(CONF_COMMUNITY)
    baseoid: str = config[CONF_BASEOID]
    command_oid: str | None = config.get(CONF_COMMAND_OID)
    command_payload_on: str | None = config.get(CONF_COMMAND_PAYLOAD_ON)
    command_payload_off: str | None = config.get(CONF_COMMAND_PAYLOAD_OFF)
    version: str = config[CONF_VERSION]
    username = config.get(CONF_USERNAME)
    authkey = config.get(CONF_AUTH_KEY)
    authproto: str = config[CONF_AUTH_PROTOCOL]
    privkey = config.get(CONF_PRIV_KEY)
    privproto: str = config[CONF_PRIV_PROTOCOL]
    payload_on: str = config[CONF_PAYLOAD_ON]
    payload_off: str = config[CONF_PAYLOAD_OFF]
    vartype: str = config[CONF_VARTYPE]

    if version == "3":
        if not authkey:
            authproto = "none"
        if not privkey:
            privproto = "none"

        auth_data = UsmUserData(
            username,
            authKey=authkey or None,
            privKey=privkey or None,
            authProtocol=getattr(hlapi, MAP_AUTH_PROTOCOLS[authproto]),
            privProtocol=getattr(hlapi, MAP_PRIV_PROTOCOLS[privproto]),
        )
    else:
        auth_data = CommunityData(community, mpModel=SNMP_VERSIONS[version])

    transport = UdpTransportTarget((host, port))
    request_args = await async_create_request_cmd_args(
        hass, auth_data, transport, baseoid
    )
    command_args = await async_create_command_cmd_args(hass, auth_data, transport)

    async_add_entities(
        [
            SnmpSwitch(
                name,
                host,
                port,
                baseoid,
                command_oid,
                payload_on,
                payload_off,
                command_payload_on,
                command_payload_off,
                vartype,
                request_args,
                command_args,
            )
        ],
        True,
    )


class SnmpSwitch(SwitchEntity):
    """Representation of a SNMP switch."""

    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        baseoid: str,
        commandoid: str | None,
        payload_on: str,
        payload_off: str,
        command_payload_on: str | None,
        command_payload_off: str | None,
        vartype: str,
        request_args: RequestArgsType,
        command_args: CommandArgsType,
    ) -> None:
        """Initialize the switch."""

        self._attr_name = name
        self._baseoid = baseoid
        self._vartype = vartype

        # Set the command OID to the base OID if command OID is unset
        self._commandoid = commandoid or baseoid
        self._command_payload_on = command_payload_on or payload_on
        self._command_payload_off = command_payload_off or payload_off

        self._state: bool | None = None
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._target = UdpTransportTarget((host, port))
        self._request_args = request_args
        self._command_args = command_args

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        # If vartype set, use it - https://www.pysnmp.com/pysnmp/docs/api-reference.html#pysnmp.smi.rfc1902.ObjectType
        await self._execute_command(self._command_payload_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._execute_command(self._command_payload_off)

    async def _execute_command(self, command: str) -> None:
        # User did not set vartype and command is not a digit
        if self._vartype == "none" and not self._command_payload_on.isdigit():
            await self._set(command)
        # User set vartype Null, command must be an empty string
        elif self._vartype == "Null":
            await self._set("")
        # user did not set vartype but command is digit: defaulting to Integer
        # or user did set vartype
        else:
            await self._set(MAP_SNMP_VARTYPES.get(self._vartype, Integer)(command))

    async def async_update(self) -> None:
        """Update the state."""
        get_result = await getCmd(*self._request_args)
        errindication, errstatus, errindex, restable = get_result

        if errindication:
            _LOGGER.error("SNMP error: %s", errindication)
        elif errstatus:
            _LOGGER.error(
                "SNMP error: %s at %s",
                errstatus.prettyPrint(),
                errindex and restable[-1][int(errindex) - 1] or "?",
            )
        else:
            for resrow in restable:
                if resrow[-1] == self._payload_on or resrow[-1] == Integer(
                    self._payload_on
                ):
                    self._state = True
                elif resrow[-1] == self._payload_off or resrow[-1] == Integer(
                    self._payload_off
                ):
                    self._state = False
                else:
                    _LOGGER.warning(
                        "Invalid payload '%s' received for entity %s, state is unknown",
                        resrow[-1],
                        self.entity_id,
                    )
                    self._state = None

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on; False if off. None if unknown."""
        return self._state

    async def _set(self, value: Any) -> None:
        """Set the state of the switch."""
        await setCmd(
            *self._command_args, ObjectType(ObjectIdentity(self._commandoid), value)
        )
