"""Representation of Z-Wave sensors."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import cast

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass, ConfigurationValueType, NodeStatus
from zwave_js_server.const.command_class.meter import (
    RESET_METER_OPTION_TARGET_VALUE,
    RESET_METER_OPTION_TYPE,
)
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import ConfigurationValue
from zwave_js_server.util.command_class.meter import get_meter_type

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.zwave_js.discovery_data_template import (
    NumericSensorDataTemplateData,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ENTITY_CATEGORY_DIAGNOSTIC,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_METER_TYPE,
    ATTR_METER_TYPE_NAME,
    ATTR_VALUE,
    DATA_CLIENT,
    DOMAIN,
    ENTITY_DESC_KEY_BATTERY,
    ENTITY_DESC_KEY_CO,
    ENTITY_DESC_KEY_CO2,
    ENTITY_DESC_KEY_CURRENT,
    ENTITY_DESC_KEY_ENERGY_MEASUREMENT,
    ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING,
    ENTITY_DESC_KEY_HUMIDITY,
    ENTITY_DESC_KEY_ILLUMINANCE,
    ENTITY_DESC_KEY_MEASUREMENT,
    ENTITY_DESC_KEY_POWER,
    ENTITY_DESC_KEY_POWER_FACTOR,
    ENTITY_DESC_KEY_PRESSURE,
    ENTITY_DESC_KEY_SIGNAL_STRENGTH,
    ENTITY_DESC_KEY_TARGET_TEMPERATURE,
    ENTITY_DESC_KEY_TEMPERATURE,
    ENTITY_DESC_KEY_TOTAL_INCREASING,
    ENTITY_DESC_KEY_VOLTAGE,
    SERVICE_RESET_METER,
)
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity
from .helpers import get_device_id

LOGGER = logging.getLogger(__name__)

STATUS_ICON: dict[NodeStatus, str] = {
    NodeStatus.ALIVE: "mdi:heart-pulse",
    NodeStatus.ASLEEP: "mdi:sleep",
    NodeStatus.AWAKE: "mdi:eye",
    NodeStatus.DEAD: "mdi:robot-dead",
    NodeStatus.UNKNOWN: "mdi:help-rhombus",
}


ENTITY_DESCRIPTION_KEY_MAP: dict[str, SensorEntityDescription] = {
    ENTITY_DESC_KEY_BATTERY: SensorEntityDescription(
        ENTITY_DESC_KEY_BATTERY,
        device_class=DEVICE_CLASS_BATTERY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_CURRENT: SensorEntityDescription(
        ENTITY_DESC_KEY_CURRENT,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_VOLTAGE: SensorEntityDescription(
        ENTITY_DESC_KEY_VOLTAGE,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_ENERGY_MEASUREMENT: SensorEntityDescription(
        ENTITY_DESC_KEY_ENERGY_MEASUREMENT,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING: SensorEntityDescription(
        ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    ENTITY_DESC_KEY_POWER: SensorEntityDescription(
        ENTITY_DESC_KEY_POWER,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_POWER_FACTOR: SensorEntityDescription(
        ENTITY_DESC_KEY_POWER_FACTOR,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_CO: SensorEntityDescription(
        ENTITY_DESC_KEY_CO,
        device_class=DEVICE_CLASS_CO,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_CO2: SensorEntityDescription(
        ENTITY_DESC_KEY_CO2,
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_HUMIDITY: SensorEntityDescription(
        ENTITY_DESC_KEY_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_ILLUMINANCE: SensorEntityDescription(
        ENTITY_DESC_KEY_ILLUMINANCE,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_PRESSURE: SensorEntityDescription(
        ENTITY_DESC_KEY_PRESSURE,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_SIGNAL_STRENGTH: SensorEntityDescription(
        ENTITY_DESC_KEY_SIGNAL_STRENGTH,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_TEMPERATURE: SensorEntityDescription(
        ENTITY_DESC_KEY_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_TARGET_TEMPERATURE: SensorEntityDescription(
        ENTITY_DESC_KEY_TARGET_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=None,
    ),
    ENTITY_DESC_KEY_MEASUREMENT: SensorEntityDescription(
        ENTITY_DESC_KEY_MEASUREMENT,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ENTITY_DESC_KEY_TOTAL_INCREASING: SensorEntityDescription(
        ENTITY_DESC_KEY_TOTAL_INCREASING,
        device_class=None,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_sensor(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Sensor."""
        entities: list[ZWaveBaseEntity] = []

        if info.platform_data:
            data: NumericSensorDataTemplateData = info.platform_data
        else:
            data = NumericSensorDataTemplateData()
        entity_description = ENTITY_DESCRIPTION_KEY_MAP.get(
            data.entity_description_key or "", SensorEntityDescription("base_sensor")
        )

        if info.platform_hint == "string_sensor":
            entities.append(
                ZWaveStringSensor(config_entry, client, info, entity_description)
            )
        elif info.platform_hint == "numeric_sensor":
            entities.append(
                ZWaveNumericSensor(
                    config_entry,
                    client,
                    info,
                    entity_description,
                    data.unit_of_measurement,
                )
            )
        elif info.platform_hint == "list_sensor":
            entities.append(
                ZWaveListSensor(config_entry, client, info, entity_description)
            )
        elif info.platform_hint == "config_parameter":
            entities.append(
                ZWaveConfigParameterSensor(
                    config_entry, client, info, entity_description
                )
            )
        elif info.platform_hint == "meter":
            entities.append(
                ZWaveMeterSensor(config_entry, client, info, entity_description)
            )
        else:
            LOGGER.warning(
                "Sensor not implemented for %s/%s",
                info.platform_hint,
                info.primary_value.propertyname,
            )
            return

        async_add_entities(entities)

    @callback
    def async_add_node_status_sensor(node: ZwaveNode) -> None:
        """Add node status sensor."""
        async_add_entities([ZWaveNodeStatusSensor(config_entry, client, node)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SENSOR_DOMAIN}",
            async_add_sensor,
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_node_status_sensor",
            async_add_node_status_sensor,
        )
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RESET_METER,
        {
            vol.Optional(ATTR_METER_TYPE): vol.Coerce(int),
            vol.Optional(ATTR_VALUE): vol.Coerce(int),
        },
        "async_reset_meter",
    )


class ZwaveSensorBase(ZWaveBaseEntity, SensorEntity):
    """Basic Representation of a Z-Wave sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
        entity_description: SensorEntityDescription,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize a ZWaveSensorBase entity."""
        super().__init__(config_entry, client, info)
        self.entity_description = entity_description
        self._attr_native_unit_of_measurement = unit_of_measurement

        # Entity class attributes
        self._attr_force_update = True
        self._attr_name = self.generate_name(include_value_name=True)


class ZWaveStringSensor(ZwaveSensorBase):
    """Representation of a Z-Wave String sensor."""

    @property
    def native_value(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        return str(self.info.primary_value.value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement the value is expressed in."""
        if self.info.primary_value.metadata.unit is None:
            return None
        return str(self.info.primary_value.metadata.unit)


class ZWaveNumericSensor(ZwaveSensorBase):
    """Representation of a Z-Wave Numeric sensor."""

    @property
    def native_value(self) -> float:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return 0
        return round(float(self.info.primary_value.value), 2)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement the value is expressed in."""
        if self._attr_native_unit_of_measurement is not None:
            return self._attr_native_unit_of_measurement
        if self.info.primary_value.metadata.unit is None:
            return None

        return str(self.info.primary_value.metadata.unit)


class ZWaveMeterSensor(ZWaveNumericSensor):
    """Representation of a Z-Wave Meter CC sensor."""

    @property
    def extra_state_attributes(self) -> Mapping[str, int | str] | None:
        """Return extra state attributes."""
        if meter_type := get_meter_type(self.info.primary_value):
            return {
                ATTR_METER_TYPE: meter_type.value,
                ATTR_METER_TYPE_NAME: meter_type.name,
            }
        return None

    async def async_reset_meter(
        self, meter_type: int | None = None, value: int | None = None
    ) -> None:
        """Reset meter(s) on device."""
        node = self.info.node
        primary_value = self.info.primary_value
        options = {}
        if meter_type is not None:
            options[RESET_METER_OPTION_TYPE] = meter_type
        if value is not None:
            options[RESET_METER_OPTION_TARGET_VALUE] = value
        args = [options] if options else []
        await node.endpoints[primary_value.endpoint].async_invoke_cc_api(
            CommandClass.METER, "reset", *args, wait_for_result=False
        )
        LOGGER.debug(
            "Meters on node %s endpoint %s reset with the following options: %s",
            node,
            primary_value.endpoint,
            options,
        )


class ZWaveListSensor(ZwaveSensorBase):
    """Representation of a Z-Wave Numeric sensor with multiple states."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
        entity_description: SensorEntityDescription,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize a ZWaveListSensor entity."""
        super().__init__(
            config_entry, client, info, entity_description, unit_of_measurement
        )

        # Entity class attributes
        self._attr_name = self.generate_name(
            include_value_name=True,
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[self.info.primary_value.property_key_name],
        )

    @property
    def native_value(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        if (
            str(self.info.primary_value.value)
            not in self.info.primary_value.metadata.states
        ):
            return str(self.info.primary_value.value)
        return str(
            self.info.primary_value.metadata.states[str(self.info.primary_value.value)]
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device specific state attributes."""
        # add the value's int value as property for multi-value (list) items
        return {ATTR_VALUE: self.info.primary_value.value}


class ZWaveConfigParameterSensor(ZwaveSensorBase):
    """Representation of a Z-Wave config parameter sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
        entity_description: SensorEntityDescription,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize a ZWaveConfigParameterSensor entity."""
        super().__init__(
            config_entry, client, info, entity_description, unit_of_measurement
        )
        self._primary_value = cast(ConfigurationValue, self.info.primary_value)

        # Entity class attributes
        self._attr_name = self.generate_name(
            include_value_name=True,
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[self.info.primary_value.property_key_name],
            name_suffix="Config Parameter",
        )

    @property
    def native_value(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        if (
            self._primary_value.configuration_value_type == ConfigurationValueType.RANGE
            or (
                not str(self.info.primary_value.value)
                in self.info.primary_value.metadata.states
            )
        ):
            return str(self.info.primary_value.value)
        return str(
            self.info.primary_value.metadata.states[str(self.info.primary_value.value)]
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device specific state attributes."""
        if self._primary_value.configuration_value_type == ConfigurationValueType.RANGE:
            return None
        # add the value's int value as property for multi-value (list) items
        return {ATTR_VALUE: self.info.primary_value.value}


class ZWaveNodeStatusSensor(SensorEntity):
    """Representation of a node status sensor."""

    _attr_should_poll = False
    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, node: ZwaveNode
    ) -> None:
        """Initialize a generic Z-Wave device entity."""
        self.config_entry = config_entry
        self.client = client
        self.node = node
        name: str = (
            self.node.name
            or self.node.device_config.description
            or f"Node {self.node.node_id}"
        )
        # Entity class attributes
        self._attr_name = f"{name}: Node Status"
        self._attr_unique_id = (
            f"{self.client.driver.controller.home_id}.{node.node_id}.node_status"
        )
        # device is precreated in main handler
        self._attr_device_info = DeviceInfo(
            identifiers={get_device_id(self.client, self.node)},
        )
        self._attr_native_value: str = node.status.name.lower()

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        # pylint: disable=no-self-use
        raise ValueError("There is no value to poll for this entity")

    @callback
    def _status_changed(self, _: dict) -> None:
        """Call when status event is received."""
        self._attr_native_value = self.node.status.name.lower()
        self.async_write_ha_state()

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        return STATUS_ICON[self.node.status]

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        # Add value_changed callbacks.
        for evt in ("wake up", "sleep", "dead", "alive"):
            self.async_on_remove(self.node.on(evt, self._status_changed))
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.unique_id}_poll_value",
                self.async_poll_value,
            )
        )
        self.async_write_ha_state()
