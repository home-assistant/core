"""
Support for SNMP enabled switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.snmp/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_PAYLOAD_ON, CONF_PAYLOAD_OFF,
    CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pysnmp==4.4.5']

_LOGGER = logging.getLogger(__name__)

CONF_BASEOID = 'baseoid'
CONF_COMMAND_OID = 'command_oid'
CONF_COMMAND_PAYLOAD_ON = 'command_payload_on'
CONF_COMMAND_PAYLOAD_OFF = 'command_payload_off'
CONF_COMMUNITY = 'community'
CONF_VERSION = 'version'
CONF_AUTH_KEY = 'auth_key'
CONF_AUTH_PROTOCOL = 'auth_protocol'
CONF_PRIV_KEY = 'priv_key'
CONF_PRIV_PROTOCOL = 'priv_protocol'

DEFAULT_NAME = 'SNMP Switch'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = '161'
DEFAULT_COMMUNITY = 'private'
DEFAULT_VERSION = '1'
DEFAULT_AUTH_PROTOCOL = 'none'
DEFAULT_PRIV_PROTOCOL = 'none'
DEFAULT_PAYLOAD_ON = 1
DEFAULT_PAYLOAD_OFF = 0

SNMP_VERSIONS = {
    '1': 0,
    '2c': 1,
    '3': None
}

MAP_AUTH_PROTOCOLS = {
    'none': 'usmNoAuthProtocol',
    'hmac-md5': 'usmHMACMD5AuthProtocol',
    'hmac-sha': 'usmHMACSHAAuthProtocol',
    'hmac128-sha224': 'usmHMAC128SHA224AuthProtocol',
    'hmac192-sha256': 'usmHMAC192SHA256AuthProtocol',
    'hmac256-sha384': 'usmHMAC256SHA384AuthProtocol',
    'hmac384-sha512': 'usmHMAC384SHA512AuthProtocol',
}

MAP_PRIV_PROTOCOLS = {
    'none': 'usmNoPrivProtocol',
    'des': 'usmDESPrivProtocol',
    '3des-ede': 'usm3DESEDEPrivProtocol',
    'aes-cfb-128': 'usmAesCfb128Protocol',
    'aes-cfb-192': 'usmAesCfb192Protocol',
    'aes-cfb-256': 'usmAesCfb256Protocol',
}

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
            CommunityData, ContextData, SnmpEngine,
            UdpTransportTarget, UsmUserData)

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
        from pysnmp.hlapi.asyncio import (getCmd, ObjectType, ObjectIdentity)
        from pyasn1.type.univ import (Integer)

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
        from pysnmp.hlapi.asyncio import (setCmd, ObjectType, ObjectIdentity)

        await setCmd(
            *self._request_args,
            ObjectType(ObjectIdentity(self._commandoid), value)
        )
