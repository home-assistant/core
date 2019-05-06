"""Support for SNMP enabled switch."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON, CONF_PORT,
    CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AUTH_KEY, CONF_AUTH_PROTOCOL, CONF_BASEOID, CONF_COMMUNITY,
    CONF_PRIV_KEY, CONF_PRIV_PROTOCOL, CONF_VERSION, DEFAULT_AUTH_PROTOCOL,
    DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_PRIV_PROTOCOL,
    DEFAULT_VERSION, MAP_AUTH_PROTOCOLS, MAP_PRIV_PROTOCOLS, SNMP_VERSIONS)

_LOGGER = logging.getLogger(__name__)

CONF_COMMAND_OID = 'command_oid'
CONF_COMMAND_PAYLOAD_OFF = 'command_payload_off'
CONF_COMMAND_PAYLOAD_ON = 'command_payload_on'

DEFAULT_COMMUNITY = 'private'
DEFAULT_PAYLOAD_OFF = 0
DEFAULT_PAYLOAD_ON = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
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
    vol.Optional(CONF_AUTH_PROTOCOL, default=DEFAULT_AUTH_PROTOCOL):
        vol.In(MAP_AUTH_PROTOCOLS),
    vol.Optional(CONF_PRIV_KEY): cv.string,
    vol.Optional(CONF_PRIV_PROTOCOL, default=DEFAULT_PRIV_PROTOCOL):
        vol.In(MAP_PRIV_PROTOCOLS),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the SNMP switch."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    community = config.get(CONF_COMMUNITY)
    baseoid = config.get(CONF_BASEOID)
    command_oid = config.get(CONF_COMMAND_OID)
    command_payload_on = config.get(CONF_COMMAND_PAYLOAD_ON)
    command_payload_off = config.get(CONF_COMMAND_PAYLOAD_OFF)
    version = config.get(CONF_VERSION)
    username = config.get(CONF_USERNAME)
    authkey = config.get(CONF_AUTH_KEY)
    authproto = config.get(CONF_AUTH_PROTOCOL)
    privkey = config.get(CONF_PRIV_KEY)
    privproto = config.get(CONF_PRIV_PROTOCOL)
    payload_on = config.get(CONF_PAYLOAD_ON)
    payload_off = config.get(CONF_PAYLOAD_OFF)

    async_add_entities(
        [SnmpSwitch(
            name, host, port, community, baseoid, command_oid, version,
            username, authkey, authproto, privkey, privproto, payload_on,
            payload_off, command_payload_on, command_payload_off)], True)


class SnmpSwitch(SwitchDevice):
    """Representation of a SNMP switch."""

    def __init__(self, name, host, port, community, baseoid, commandoid,
                 version, username, authkey, authproto, privkey, privproto,
                 payload_on, payload_off, command_payload_on,
                 command_payload_off):
        """Initialize the switch."""
        from pysnmp.hlapi.asyncio import (
            CommunityData, ContextData, SnmpEngine, UdpTransportTarget,
            UsmUserData)

        self._name = name
        self._baseoid = baseoid

        # Set the command OID to the base OID if command OID is unset
        self._commandoid = commandoid or baseoid
        self._command_payload_on = command_payload_on or payload_on
        self._command_payload_off = command_payload_off or payload_off

        self._state = None
        self._payload_on = payload_on
        self._payload_off = payload_off

        if version == '3':
            import pysnmp.hlapi.asyncio as hlapi

            if not authkey:
                authproto = 'none'
            if not privkey:
                privproto = 'none'

            self._request_args = [
                SnmpEngine(),
                UsmUserData(
                    username,
                    authKey=authkey or None,
                    privKey=privkey or None,
                    authProtocol=getattr(hlapi, MAP_AUTH_PROTOCOLS[authproto]),
                    privProtocol=getattr(hlapi, MAP_PRIV_PROTOCOLS[privproto]),
                ),
                UdpTransportTarget((host, port)),
                ContextData(),
            ]
        else:
            self._request_args = [
                SnmpEngine(),
                CommunityData(community, mpModel=SNMP_VERSIONS[version]),
                UdpTransportTarget((host, port)),
                ContextData(),
            ]

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        from pyasn1.type.univ import (Integer)

        await self._set(Integer(self._command_payload_on))

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        from pyasn1.type.univ import (Integer)

        await self._set(Integer(self._command_payload_off))

    async def async_update(self):
        """Update the state."""
        from pysnmp.hlapi.asyncio import getCmd, ObjectType, ObjectIdentity
        from pyasn1.type.univ import Integer

        errindication, errstatus, errindex, restable = await getCmd(
            *self._request_args, ObjectType(ObjectIdentity(self._baseoid)))

        if errindication:
            _LOGGER.error("SNMP error: %s", errindication)
        elif errstatus:
            _LOGGER.error("SNMP error: %s at %s", errstatus.prettyPrint(),
                          errindex and restable[-1][int(errindex) - 1] or '?')
        else:
            for resrow in restable:
                if resrow[-1] == Integer(self._payload_on):
                    self._state = True
                elif resrow[-1] == Integer(self._payload_off):
                    self._state = False
                else:
                    self._state = None

    @property
    def name(self):
        """Return the switch's name."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on; False if off. None if unknown."""
        return self._state

    async def _set(self, value):
        from pysnmp.hlapi.asyncio import setCmd, ObjectType, ObjectIdentity

        await setCmd(
            *self._request_args,
            ObjectType(ObjectIdentity(self._commandoid), value)
        )
