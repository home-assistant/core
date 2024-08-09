"""Support for Zabbix sensors."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any, Final, cast

import voluptuous as vol
from zabbix_utils import APIRequestError, ProcessingError, ZabbixAPI

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SENSORS, CONF_URL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_SENSOR_TRIGGERS,
    CONF_SENSOR_TRIGGERS_HOSTIDS,
    CONF_SENSOR_TRIGGERS_INDIVIDUAL,
    CONF_SENSOR_TRIGGERS_NAME,
    DEFAULT_TRIGGER_NAME,
    DOMAIN,
    ZAPI,
)

_LOGGER = logging.getLogger(__name__)

_ZABBIX_ID_LIST_SCHEMA = vol.Schema([int])
_ZABBIX_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SENSOR_TRIGGERS_HOSTIDS, default=[]): _ZABBIX_ID_LIST_SCHEMA,
        vol.Optional(CONF_SENSOR_TRIGGERS_INDIVIDUAL, default=False): cv.boolean,
        vol.Optional(CONF_SENSOR_TRIGGERS_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSOR_TRIGGERS): vol.Any(_ZABBIX_TRIGGER_SCHEMA, None)}
)


async def async_zabbix_sensors(
    hass: HomeAssistant,
    config: ConfigType,
    entry_id: str | None = None,
) -> list[ZabbixTriggerCountSensor] | None:
    """Set up Zabbix sensors."""
    sensors: list[ZabbixTriggerCountSensor] = []
    configuration_url: str | None = None

    if entry_id is None:
        # this is from configuration.yaml
        zapi: ZabbixAPI
        if not (zapi := hass.data[DOMAIN].get(ZAPI)):
            _LOGGER.error("Zabbix integration hasn't been loaded? zapi is None")
            return None
        entry_id = "configuration"
        configuration_url = hass.data[DOMAIN].get(CONF_HOST)
    elif not (zapi := hass.data[DOMAIN][entry_id].get(ZAPI)):
        _LOGGER.error("Zabbix integration hasn't been loaded? zapi is None")
        return None
    if configuration_url is None:
        configuration_url = hass.data[DOMAIN][entry_id].get(CONF_URL)
    _LOGGER.info("Connected to Zabbix API Version %s", zapi.api_version())

    # The following code seems overly complex. Need to think about this...
    if trigger_conf := config.get(CONF_SENSOR_TRIGGERS):
        hostids: list[str] = cast(
            list[str], trigger_conf.get(CONF_SENSOR_TRIGGERS_HOSTIDS, [])
        )
        individual: bool = cast(
            bool, trigger_conf.get(CONF_SENSOR_TRIGGERS_INDIVIDUAL, False)
        )
        name: str = cast(
            str, trigger_conf.get(CONF_SENSOR_TRIGGERS_NAME, DEFAULT_TRIGGER_NAME)
        )
        if name is None or name == "":
            name = DEFAULT_TRIGGER_NAME

        if individual:
            # Individual sensor per host
            if not hostids or len(hostids) == 0:
                # We need hostids
                _LOGGER.error("If using 'individual', must specify hostids")
                return None

            for hostid in hostids:
                _LOGGER.debug("Creating Zabbix Sensor: %s", str(hostid))
                # get hostname from hostid
                try:
                    result: Any | None = await hass.async_add_executor_job(
                        lambda local_hostid: zapi.host.get(
                            hostids=local_hostid, output="extend"
                        ),
                        hostid,
                    )
                    assert isinstance(result, list)
                    name = result[0].get("name")
                    zabbix_sensor = ZabbixTriggerCountSensor(
                        zapi,
                        name,
                        entry_id,
                        configuration_url,
                        ZabbixTriggerCountSensorType.SINGLE_HOST_TYPE,
                        [hostid],
                    )
                    sensors.append(zabbix_sensor)
                except (APIRequestError, ProcessingError) as e:
                    _LOGGER.error(
                        "Error getting hostname for hostid: %s. Error message: %s",
                        str(hostid),
                        str(e),
                    )
        elif not hostids or len(hostids) == 0:
            # Single sensor that provides the total count of triggers.
            _LOGGER.debug("Creating Zabbix Sensor")
            zabbix_sensor = ZabbixTriggerCountSensor(
                zapi, name, entry_id, configuration_url
            )
            sensors.append(zabbix_sensor)
        else:
            # Single sensor that sums total issues for all hosts
            _LOGGER.debug("Creating Zabbix Sensor group: %s", str(hostids))
            try:
                if name == DEFAULT_TRIGGER_NAME:
                    name = " ".join(
                        name["name"]
                        for name in await hass.async_add_executor_job(
                            lambda: zapi.host.get(hostids=hostids, output="extend")
                        )
                    )
                zabbix_sensor = ZabbixTriggerCountSensor(
                    zapi,
                    name,
                    entry_id,
                    configuration_url,
                    ZabbixTriggerCountSensorType.MULTIPLE_HOST_TYPE,
                    hostids,
                )
                sensors.append(zabbix_sensor)
            except (APIRequestError, ProcessingError) as e:
                _LOGGER.error(
                    "Error getting hostnames for hostids: %s. Error message: %s",
                    str(hostids),
                    str(e),
                )
    else:
        # Single sensor that provides the total count of triggers.
        _LOGGER.debug("Creating Zabbix Sensor")
        zabbix_sensor = ZabbixTriggerCountSensor(
            zapi, DEFAULT_TRIGGER_NAME, entry_id, configuration_url
        )
        sensors.append(zabbix_sensor)

    return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    for entry in hass.data[DOMAIN][config_entry.entry_id][CONF_SENSORS]:
        sensors: list[ZabbixTriggerCountSensor] | None = await async_zabbix_sensors(
            hass, entry, config_entry.entry_id
        )
        if sensors is not None:
            async_add_entities(sensors, update_before_add=True)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    sensors: list[ZabbixTriggerCountSensor] | None = await async_zabbix_sensors(
        hass, config
    )
    if sensors is not None:
        async_add_entities(sensors, update_before_add=True)


class ZabbixTriggerCountSensorType(StrEnum):
    """Type of Zabbix sensors."""

    DEFAULT_TYPE: Final = "default"
    SINGLE_HOST_TYPE: Final = "single_host"
    MULTIPLE_HOST_TYPE: Final = "mnultiple_hosts"


class ZabbixTriggerCountSensor(SensorEntity):
    """Get the active trigger count for all Zabbix monitored hosts."""

    _attr_has_entity_name = True
    sensor_index: int = 0

    def __init__(
        self,
        zapi: ZabbixAPI,
        name: str,
        entry_id: str,
        configuration_url: str,
        sensor_type: ZabbixTriggerCountSensorType = ZabbixTriggerCountSensorType.DEFAULT_TYPE,
        hostids: list[str] | None = None,
    ) -> None:
        """Initialize."""
        self.zapi: ZabbixAPI = zapi
        self._attr_name = name
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = "issues"
        self._attr_available = True
        self.sensor_type: ZabbixTriggerCountSensorType = sensor_type
        self.hostids: list[str] | None = hostids
        self._attr_attributes: Mapping[str, Any]
        if self.sensor_type == ZabbixTriggerCountSensorType.SINGLE_HOST_TYPE:
            self._attr_attributes = {"Host ID": self.hostids}
        elif self.sensor_type == ZabbixTriggerCountSensorType.MULTIPLE_HOST_TYPE:
            self._attr_attributes = {"Host IDs": self.hostids}
        else:
            self._attr_attributes = {"Host IDs": "All"}
        self.entity_id = SENSOR_DOMAIN + "." + DOMAIN + "_" + name
        ZabbixTriggerCountSensor.sensor_index += 1
        self._attr_unique_id = (
            f"{entry_id}:{ZabbixTriggerCountSensor.sensor_index}-{name}"
        )
        self._attr_device_info = DeviceInfo(
            name="Zabbix",
            configuration_url=configuration_url,
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self) -> None:
        """Update the sensor."""

        _LOGGER.debug("Updating ZabbixTriggerCountSensor: %s", str(self._attr_name))
        try:
            if self.sensor_type in (
                ZabbixTriggerCountSensorType.SINGLE_HOST_TYPE,
                ZabbixTriggerCountSensorType.MULTIPLE_HOST_TYPE,
            ):
                triggers: list = await self.hass.async_add_executor_job(
                    lambda: self.zapi.trigger.get(
                        hostids=self.hostids,
                        output="extend",
                        only_true=1,
                        monitored=1,
                        filter={"value": 1},
                    )
                )
            else:
                triggers = await self.hass.async_add_executor_job(
                    lambda: self.zapi.trigger.get(
                        output="extend", only_true=1, monitored=1, filter={"value": 1}
                    )
                )
            assert isinstance(triggers, list)
            self._attr_native_value = str(len(triggers))
            self._attr_available = True
        except (APIRequestError, ProcessingError) as e:
            self._attr_available = False
            _LOGGER.error(
                "Error updating ZabbixTriggerCountSensor: %s. Error message: %s",
                str(self._attr_name),
                str(e),
            )
