"""
Support for SNMP enabled switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.snmp/
"""

import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_NAME, CONF_PORT,
                                 CONF_PAYLOAD_ON, CONF_PAYLOAD_OFF)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pysnmp==4.3.10']

_LOGGER = logging.getLogger(__name__)

CONF_BASEOID = 'baseoid'
CONF_COMMUNITY = 'community'
CONF_VERSION = 'version'

DEFAULT_NAME = 'SNMPSwitch'
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
    vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_VERSION, default=DEFAULT_VERSION):
        vol.In(SNMP_VERSIONS),
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SNMP switch."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    community = config.get(CONF_COMMUNITY)
    baseoid = config.get(CONF_BASEOID)
    version = config.get(CONF_VERSION)
    payload_on = config.get(CONF_PAYLOAD_ON)
    payload_off = config.get(CONF_PAYLOAD_OFF)

    data = SnmpCommand(host, port, community, baseoid, version, payload_on,
                       payload_off)
    add_devices([SnmpSwitch(data, name)], True)


class SnmpSwitch(SwitchDevice):
    """Represents a SNMP switch."""

    def __init__(self, snmp_command, name):
        """Initialize the switch."""
        self._cmd = snmp_command
        self._name = name

    def turn_on(self):
        """Turn on the switch."""
        self._cmd.turn_on()

    def turn_off(self):
        """Turn off the switch."""
        self._cmd.turn_off()

    def update(self):
        """Update the state."""
        self._cmd.update()

    @property
    def name(self):
        """Return the switch's name."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on; False otherwise."""
        return self._cmd.state


class SnmpCommand(object):
    """Turn on/off the switch and update the states."""

    def __init__(self, host, port, community, baseoid,
                 version, payload_on, payload_off):
        """Initialize the data object."""
        self._host = host
        self._port = port
        self._community = community
        self._baseoid = baseoid
        self._version = SNMP_VERSIONS[version]
        self._state = None
        self._payload_on = payload_on
        self._payload_off = payload_off

    def update(self):
        """Get the latest data from the remote SNMP capable host."""
        from pysnmp.hlapi import (
            getCmd, CommunityData, SnmpEngine, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity)

        g = getCmd(SnmpEngine(),
                   CommunityData(self._community, mpModel=self._version),
                   UdpTransportTarget((self._host, self._port)),
                   ContextData(),
                   ObjectType(ObjectIdentity(self._baseoid)))

        errindication, errstatus, errindex, restable = next(g)

        if errindication:
            _LOGGER.error("SNMP error: %s", errindication)
        elif errstatus:
            _LOGGER.error("SNMP error: %s at %s", errstatus.prettyPrint(),
                          errindex and restable[-1][int(errindex) - 1] or '?')
        else:
            for resrow in restable:
                if resrow[-1] == self._typecast(self._payload_on):
                    self._state = True
                elif resrow[-1] == self._typecast(self._payload_off):
                    self._state = False
                else:
                    self._state = None

    def turn_on(self):
        """Send SNMP set command to the switch to turn it on."""
        from pysnmp.hlapi import (
            setCmd, CommunityData, SnmpEngine, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity)

        request = setCmd(
            SnmpEngine(),
            CommunityData(self._community, mpModel=self._version),
            UdpTransportTarget((self._host, self._port)),
            ContextData(),
            ObjectType(ObjectIdentity(self._baseoid),
                       self._typecast(self._payload_on))
        )

        next(request)

    def turn_off(self):
        """Send SNMP set command to the switch to turn it off."""
        from pysnmp.hlapi import (
            setCmd, CommunityData, SnmpEngine, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity)

        request = setCmd(
            SnmpEngine(),
            CommunityData(self._community, mpModel=self._version),
            UdpTransportTarget((self._host, self._port)),
            ContextData(),
            ObjectType(ObjectIdentity(self._baseoid),
                       self._typecast(self._payload_off))
        )

        next(request)

    @property
    def state(self):
        """Return the switch's state."""
        if self._state == self._payload_on:
            return True

        return False

    def _typecast(self, payload):
        """Convert from python to SNMP type."""
        from pyasn1.type.univ import (Integer)

        return Integer(payload)
