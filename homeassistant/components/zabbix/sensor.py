"""Support for Zabbix sensors."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from zabbix_utils import ZabbixAPI

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_CONF_TRIGGERS = "triggers"
_CONF_HOSTIDS = "hostids"
_CONF_INDIVIDUAL = "individual"

_ZABBIX_ID_LIST_SCHEMA = vol.Schema([int])
_ZABBIX_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(_CONF_HOSTIDS, default=[]): _ZABBIX_ID_LIST_SCHEMA,
        vol.Optional(_CONF_INDIVIDUAL, default=False): cv.boolean,
        vol.Optional(CONF_NAME): cv.string,
    }
)

# SCAN_INTERVAL = 30
#
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(_CONF_TRIGGERS): vol.Any(_ZABBIX_TRIGGER_SCHEMA, None)}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Zabbix sensor platform."""
    sensors: list[ZabbixTriggerCountSensor] = []

    if not (zapi := hass.data[DOMAIN]):
        _LOGGER.error("Zabbix integration hasn't been loaded? zapi is None")
        return

    _LOGGER.debug("Connected to Zabbix API Version %s", zapi.api_version())

    # The following code seems overly complex. Need to think about this...
    if trigger_conf := config.get(_CONF_TRIGGERS):
        hostids = trigger_conf.get(_CONF_HOSTIDS)
        individual = trigger_conf.get(_CONF_INDIVIDUAL)
        name = trigger_conf.get(CONF_NAME)

        if individual:
            # Individual sensor per host
            if not hostids:
                # We need hostids
                _LOGGER.error("If using 'individual', must specify hostids")
                return

            for hostid in hostids:
                _LOGGER.debug("Creating Zabbix Sensor: %s", str(hostid))
                sensors.append(ZabbixSingleHostTriggerCountSensor(zapi, [hostid], name))
        elif not hostids:
            # Single sensor that provides the total count of triggers.
            _LOGGER.debug("Creating Zabbix Sensor")
            sensors.append(ZabbixTriggerCountSensor(zapi, name))
        else:
            # Single sensor that sums total issues for all hosts
            _LOGGER.debug("Creating Zabbix Sensor group: %s", str(hostids))
            sensors.append(ZabbixMultipleHostTriggerCountSensor(zapi, hostids, name))

    else:
        # Single sensor that provides the total count of triggers.
        _LOGGER.debug("Creating Zabbix Sensor")
        sensors.append(ZabbixTriggerCountSensor(zapi))

    add_entities(sensors)


class ZabbixTriggerCountSensor(SensorEntity):
    """Get the active trigger count for all Zabbix monitored hosts."""

    def __init__(self, zapi: ZabbixAPI, name: str | None = "Zabbix") -> None:
        """Initialize Zabbix sensor."""
        self._name = name
        self._zapi = zapi
        self._state: int | None = None
        self._attributes: dict[str, Any] = {}

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return "issues"

    def _call_zabbix_api(self):
        return self._zapi.trigger.get(
            output="extend", only_true=1, monitored=1, filter={"value": 1}
        )

    def update(self) -> None:
        """Update the sensor."""
        _LOGGER.debug("Updating ZabbixTriggerCountSensor: %s", str(self._name))
        triggers = self._call_zabbix_api()
        self._state = len(triggers)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the device."""
        return self._attributes


class ZabbixSingleHostTriggerCountSensor(ZabbixTriggerCountSensor):
    """Get the active trigger count for a single Zabbix monitored host."""

    def __init__(
        self, zapi: ZabbixAPI, hostid: list[str], name: str | None = None
    ) -> None:
        """Initialize Zabbix sensor."""
        super().__init__(zapi, name)
        self._hostid = hostid
        if not name:
            self._name = self._zapi.host.get(hostids=self._hostid, output="extend")[0][
                "name"
            ]

        self._attributes["Host ID"] = self._hostid

    def _call_zabbix_api(self):
        return self._zapi.trigger.get(
            hostids=self._hostid,
            output="extend",
            only_true=1,
            monitored=1,
            filter={"value": 1},
        )


class ZabbixMultipleHostTriggerCountSensor(ZabbixTriggerCountSensor):
    """Get the active trigger count for specified Zabbix monitored hosts."""

    def __init__(
        self, zapi: ZabbixAPI, hostids: list[str], name: str | None = None
    ) -> None:
        """Initialize Zabbix sensor."""
        super().__init__(zapi, name)
        self._hostids = hostids
        if not name:
            host_names = self._zapi.host.get(hostids=self._hostids, output="extend")
            self._name = " ".join(name["name"] for name in host_names)
        self._attributes["Host IDs"] = self._hostids

    def _call_zabbix_api(self):
        return self._zapi.trigger.get(
            hostids=self._hostids,
            output="extend",
            only_true=1,
            monitored=1,
            filter={"value": 1},
        )
