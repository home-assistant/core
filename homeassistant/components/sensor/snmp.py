"""
Support for displaying collected data over SNMP.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.snmp/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_UNIT_OF_MEASUREMENT, STATE_UNKNOWN,
    CONF_USERNAME, CONF_VALUE_TEMPLATE)

REQUIREMENTS = ['pysnmp==4.4.8']

_LOGGER = logging.getLogger(__name__)

CONF_BASEOID = 'baseoid'
CONF_COMMUNITY = 'community'
CONF_VERSION = 'version'
CONF_AUTH_KEY = 'auth_key'
CONF_AUTH_PROTOCOL = 'auth_protocol'
CONF_PRIV_KEY = 'priv_key'
CONF_PRIV_PROTOCOL = 'priv_protocol'
CONF_ACCEPT_ERRORS = 'accept_errors'
CONF_DEFAULT_VALUE = 'default_value'

DEFAULT_COMMUNITY = 'public'
DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'SNMP'
DEFAULT_PORT = '161'
DEFAULT_VERSION = '1'
DEFAULT_AUTH_PROTOCOL = 'none'
DEFAULT_PRIV_PROTOCOL = 'none'

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

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_BASEOID): cv.string,
    vol.Optional(CONF_ACCEPT_ERRORS, default=False): cv.boolean,
    vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
    vol.Optional(CONF_DEFAULT_VALUE): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
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
    """Set up the SNMP sensor."""
    from pysnmp.hlapi.asyncio import (
        getCmd, CommunityData, SnmpEngine, UdpTransportTarget, ContextData,
        ObjectType, ObjectIdentity, UsmUserData)

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    community = config.get(CONF_COMMUNITY)
    baseoid = config.get(CONF_BASEOID)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    version = config.get(CONF_VERSION)
    username = config.get(CONF_USERNAME)
    authkey = config.get(CONF_AUTH_KEY)
    authproto = config.get(CONF_AUTH_PROTOCOL)
    privkey = config.get(CONF_PRIV_KEY)
    privproto = config.get(CONF_PRIV_PROTOCOL)
    accept_errors = config.get(CONF_ACCEPT_ERRORS)
    default_value = config.get(CONF_DEFAULT_VALUE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if value_template is not None:
        value_template.hass = hass

    if version == '3':
        import pysnmp.hlapi.asyncio as hlapi

        if not authkey:
            authproto = 'none'
        if not privkey:
            privproto = 'none'

        request_args = [
            SnmpEngine(),
            UsmUserData(
                username, authKey=authkey or None, privKey=privkey or None,
                authProtocol=getattr(hlapi, MAP_AUTH_PROTOCOLS[authproto]),
                privProtocol=getattr(hlapi, MAP_PRIV_PROTOCOLS[privproto]),),
            UdpTransportTarget((host, port)),
            ContextData(),
        ]
    else:
        request_args = [
            SnmpEngine(),
            CommunityData(community, mpModel=SNMP_VERSIONS[version]),
            UdpTransportTarget((host, port)),
            ContextData(),
        ]

    errindication, _, _, _ = await getCmd(
        *request_args, ObjectType(ObjectIdentity(baseoid)))

    if errindication and not accept_errors:
        _LOGGER.error("Please check the details in the configuration file")
        return

    data = SnmpData(request_args, baseoid, accept_errors, default_value)
    async_add_entities([SnmpSensor(data, name, unit, value_template)], True)


class SnmpSensor(Entity):
    """Representation of a SNMP sensor."""

    def __init__(self, data, name, unit_of_measurement, value_template):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data and updates the states."""
        await self.data.async_update()
        value = self.data.value

        if value is None:
            value = STATE_UNKNOWN
        elif self._value_template is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value, STATE_UNKNOWN)

        self._state = value


class SnmpData:
    """Get the latest data and update the states."""

    def __init__(self, request_args, baseoid, accept_errors, default_value):
        """Initialize the data object."""
        self._request_args = request_args
        self._baseoid = baseoid
        self._accept_errors = accept_errors
        self._default_value = default_value
        self.value = None

    async def async_update(self):
        """Get the latest data from the remote SNMP capable host."""
        from pysnmp.hlapi.asyncio import (getCmd, ObjectType, ObjectIdentity)

        errindication, errstatus, errindex, restable = await getCmd(
            *self._request_args, ObjectType(ObjectIdentity(self._baseoid)))

        if errindication and not self._accept_errors:
            _LOGGER.error("SNMP error: %s", errindication)
        elif errstatus and not self._accept_errors:
            _LOGGER.error("SNMP error: %s at %s", errstatus.prettyPrint(),
                          errindex and restable[-1][int(errindex) - 1] or '?')
        elif (errindication or errstatus) and self._accept_errors:
            self.value = self._default_value
        else:
            for resrow in restable:
                self.value = str(resrow[-1])
