"""Support for displaying collected data over SNMP."""
from __future__ import annotations

from datetime import timedelta
import logging

import pysnmp.hlapi.asyncio as hlapi
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template_entity import (
    TEMPLATE_SENSOR_BASE_SCHEMA,
    TemplateSensor,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ACCEPT_ERRORS,
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_DEFAULT_VALUE,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
    CONF_VERSION,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BASEOID): cv.string,
        vol.Optional(CONF_ACCEPT_ERRORS, default=False): cv.boolean,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Optional(CONF_DEFAULT_VALUE): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
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
    }
).extend(TEMPLATE_SENSOR_BASE_SCHEMA.schema)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SNMP sensor."""
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
    accept_errors = config.get(CONF_ACCEPT_ERRORS)
    default_value = config.get(CONF_DEFAULT_VALUE)
    unique_id = config.get(CONF_UNIQUE_ID)

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
            UdpTransportTarget((host, port), timeout=DEFAULT_TIMEOUT),
            ContextData(),
        ]
    else:
        request_args = [
            SnmpEngine(),
            CommunityData(community, mpModel=SNMP_VERSIONS[version]),
            UdpTransportTarget((host, port), timeout=DEFAULT_TIMEOUT),
            ContextData(),
        ]

    errindication, _, _, _ = await getCmd(
        *request_args, ObjectType(ObjectIdentity(baseoid))
    )

    if errindication and not accept_errors:
        _LOGGER.error("Please check the details in the configuration file")
        return

    data = SnmpData(request_args, baseoid, accept_errors, default_value)
    async_add_entities([SnmpSensor(hass, data, config, unique_id)], True)


class SnmpSensor(TemplateSensor):
    """Representation of a SNMP sensor."""

    _attr_should_poll = True

    def __init__(self, hass, data, config, unique_id):
        """Initialize the sensor."""
        super().__init__(
            hass, config=config, unique_id=unique_id, fallback_name=DEFAULT_NAME
        )
        self.data = data
        self._state = None
        self._value_template = config.get(CONF_VALUE_TEMPLATE)
        if (value_template := self._value_template) is not None:
            value_template.hass = hass

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        await self.data.async_update()

        if (value := self.data.value) is None:
            value = STATE_UNKNOWN
        elif self._value_template is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value, STATE_UNKNOWN
            )

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

        errindication, errstatus, errindex, restable = await getCmd(
            *self._request_args, ObjectType(ObjectIdentity(self._baseoid))
        )

        if errindication and not self._accept_errors:
            _LOGGER.error("SNMP error: %s", errindication)
        elif errstatus and not self._accept_errors:
            _LOGGER.error(
                "SNMP error: %s at %s",
                errstatus.prettyPrint(),
                errindex and restable[-1][int(errindex) - 1] or "?",
            )
        elif (errindication or errstatus) and self._accept_errors:
            self.value = self._default_value
        else:
            for resrow in restable:
                self.value = resrow[-1].prettyPrint()
