"""
Support for SNMP enabled switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.snmp/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_PAYLOAD_ON, CONF_PAYLOAD_OFF)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pysnmp==4.4.4']

_LOGGER = logging.getLogger(__name__)

CONF_BASEOID = 'baseoid'
CONF_COMMAND_OID = 'command_oid'
CONF_COMMAND_PAYLOAD_ON = 'command_payload_on'
CONF_COMMAND_PAYLOAD_OFF = 'command_payload_off'
CONF_COMMUNITY = 'community'
CONF_VERSION = 'version'

DEFAULT_NAME = 'SNMP Switch'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = '161'
DEFAULT_COMMUNITY = 'private'
DEFAULT_VERSION = '1'
DEFAULT_PAYLOAD_ON = 1
DEFAULT_PAYLOAD_OFF = 0

SNMP_VERSIONS = {
    '1': 0,
    '2c': 1
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
})


def setup_platform(hass, config, add_devices, discovery_info=None):
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
    payload_on = config.get(CONF_PAYLOAD_ON)
    payload_off = config.get(CONF_PAYLOAD_OFF)

    add_devices(
        [SnmpSwitch(name, host, port, community, baseoid, command_oid, version,
                    payload_on, payload_off,
                    command_payload_on, command_payload_off)], True)


class SnmpSwitch(SwitchDevice):
    """Represents a SNMP switch."""

    def __init__(self, name, host, port, community,
                 baseoid, commandoid, version, payload_on, payload_off,
                 command_payload_on, command_payload_off):
        """Initialize the switch."""
        self._name = name
        self._host = host
        self._port = port
        self._community = community
        self._baseoid = baseoid

        """Set the command OID to the base OID if command OID is unset"""
        self._commandoid = commandoid or baseoid
        self._command_payload_on = command_payload_on or payload_on
        self._command_payload_off = command_payload_off or payload_off

        self._version = SNMP_VERSIONS[version]
        self._state = None
        self._payload_on = payload_on
        self._payload_off = payload_off

    def turn_on(self):
        """Turn on the switch."""
        from pyasn1.type.univ import (Integer)

        self._set(Integer(self._command_payload_on))

    def turn_off(self):
        """Turn off the switch."""
        from pyasn1.type.univ import (Integer)

        self._set(Integer(self._command_payload_off))

    def update(self):
        """Update the state."""
        from pysnmp.hlapi import (
            getCmd, CommunityData, SnmpEngine, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity)

        from pyasn1.type.univ import (Integer)

        request = getCmd(
            SnmpEngine(),
            CommunityData(self._community, mpModel=self._version),
            UdpTransportTarget((self._host, self._port)),
            ContextData(),
            ObjectType(ObjectIdentity(self._baseoid))
        )

        errindication, errstatus, errindex, restable = next(request)

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

    def _set(self, value):
        from pysnmp.hlapi import (
            setCmd, CommunityData, SnmpEngine, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity)

        request = setCmd(
            SnmpEngine(),
            CommunityData(self._community, mpModel=self._version),
            UdpTransportTarget((self._host, self._port)),
            ContextData(),
            ObjectType(ObjectIdentity(self._commandoid), value)
        )

        next(request)
