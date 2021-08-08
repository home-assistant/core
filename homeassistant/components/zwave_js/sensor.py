"""Representation of Z-Wave sensors."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import logging
from typing import cast

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import (
    CC_SPECIFIC_METER_TYPE,
    CC_SPECIFIC_SCALE,
    CC_SPECIFIC_SENSOR_TYPE,
    CO2_SENSORS,
    CO_SENSORS,
    CURRENT_METER_TYPES,
    CURRENT_SENSORS,
    ENERGY_METER_TYPES,
    ENERGY_SENSORS,
    HUMIDITY_SENSORS,
    ILLUMINANCE_SENSORS,
    METER_TYPE_TO_SCALE_ENUM_MAP,
    POWER_FACTOR_METER_TYPES,
    POWER_METER_TYPES,
    POWER_SENSORS,
    PRESSURE_SENSORS,
    RESET_METER_OPTION_TARGET_VALUE,
    RESET_METER_OPTION_TYPE,
    SIGNAL_STRENGTH_SENSORS,
    TEMPERATURE_SENSORS,
    TIMESTAMP_SENSORS,
    VOLTAGE_METER_TYPES,
    VOLTAGE_SENSORS,
    CommandClass,
    ConfigurationValueType,
    MeterType,
    MultilevelSensorType,
)
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import ConfigurationValue

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_METER_TYPE, ATTR_VALUE, DATA_CLIENT, DOMAIN, SERVICE_RESET_METER
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity
from .helpers import get_device_id

LOGGER = logging.getLogger(__name__)

METER_DEVICE_CLASS_MAP = {
    DEVICE_CLASS_CURRENT: CURRENT_METER_TYPES,
    DEVICE_CLASS_VOLTAGE: VOLTAGE_METER_TYPES,
    DEVICE_CLASS_ENERGY: ENERGY_METER_TYPES,
    DEVICE_CLASS_POWER: POWER_METER_TYPES,
    DEVICE_CLASS_POWER_FACTOR: POWER_FACTOR_METER_TYPES,
}

MULTILEVEL_SENSOR_DEVICE_CLASS_MAP = {
    DEVICE_CLASS_CO: CO_SENSORS,
    DEVICE_CLASS_CO2: CO2_SENSORS,
    DEVICE_CLASS_CURRENT: CURRENT_SENSORS,
    DEVICE_CLASS_ENERGY: ENERGY_SENSORS,
    DEVICE_CLASS_HUMIDITY: HUMIDITY_SENSORS,
    DEVICE_CLASS_ILLUMINANCE: ILLUMINANCE_SENSORS,
    DEVICE_CLASS_POWER: POWER_SENSORS,
    DEVICE_CLASS_PRESSURE: PRESSURE_SENSORS,
    DEVICE_CLASS_SIGNAL_STRENGTH: SIGNAL_STRENGTH_SENSORS,
    DEVICE_CLASS_TEMPERATURE: TEMPERATURE_SENSORS,
    DEVICE_CLASS_TIMESTAMP: TIMESTAMP_SENSORS,
    DEVICE_CLASS_VOLTAGE: VOLTAGE_SENSORS,
}


@dataclass
class ZwaveSensorBaseEntityDescription(SensorEntityDescription):
    """Base description of a ZwaveSensorBase entity."""

    info: ZwaveDiscoveryInfo | None = None

    def __post_init__(self) -> None:
        """Post initialize."""
        self.force_update = True

        if (device_class := self._device_class) is not None:
            self.device_class = device_class
        if (state_class := self._state_class) is not None:
            self.state_class = state_class

    @property
    def _device_class(self) -> str | None:
        """Return the device class."""
        return None

    @property
    def _state_class(self) -> str | None:
        """Return the state class."""
        return None


@dataclass
class ZwaveMeterSensorEntityDescription(ZwaveSensorBaseEntityDescription):
    """Description of a Z-Wave Meter CC entity."""

    meter_type: MeterType = field(init=False)
    scale_type: IntEnum = field(init=False)

    def __post_init__(self) -> None:
        """Post initialize."""
        assert self.info
        cc_specific = self.info.primary_value.metadata.cc_specific
        meter_type_id = cc_specific[CC_SPECIFIC_METER_TYPE]
        scale_type_id = cc_specific[CC_SPECIFIC_SCALE]
        self.meter_type = MeterType(meter_type_id)
        scale_enum = METER_TYPE_TO_SCALE_ENUM_MAP[self.meter_type]
        self.scale_type = scale_enum(scale_type_id)

        # Static values
        self.state_class = STATE_CLASS_MEASUREMENT

        super().__post_init__()

    @property
    def _device_class(self) -> str | None:
        """Return the device class."""
        for device_class, scale_type_set in METER_DEVICE_CLASS_MAP.items():
            if self.scale_type in scale_type_set:
                return device_class

        return None


@dataclass
class ZwaveMultilevelSensorEntityDescription(ZwaveSensorBaseEntityDescription):
    """Description of a Z-Wave Multilevel Sensor CC entity."""

    sensor_type: MultilevelSensorType = field(init=False)

    def __post_init__(self) -> None:
        """Post initialize."""
        assert self.info
        cc_specific = self.info.primary_value.metadata.cc_specific
        sensor_type_id = cc_specific[CC_SPECIFIC_SENSOR_TYPE]
        self.sensor_type = MultilevelSensorType(sensor_type_id)

        super().__post_init__()

    @property
    def _device_class(self) -> str | None:
        """Return the device class."""
        for device_class, sensor_type_set in MULTILEVEL_SENSOR_DEVICE_CLASS_MAP.items():
            if self.sensor_type in sensor_type_set:
                return device_class

        return None

    @property
    def _state_class(self) -> str | None:
        """Return the state class."""
        if self.sensor_type == MultilevelSensorType.TARGET_TEMPERATURE:
            return None
        return STATE_CLASS_MEASUREMENT


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

        if info.primary_value.command_class == CommandClass.BATTERY:
            entity_description = ZwaveSensorBaseEntityDescription(
                "battery",
                device_class=DEVICE_CLASS_BATTERY,
                state_class=STATE_CLASS_MEASUREMENT,
                info=info,
            )
        elif info.primary_value.command_class == CommandClass.METER:
            entity_description = ZwaveMeterSensorEntityDescription("meter", info=info)
        elif info.primary_value.command_class == CommandClass.SENSOR_MULTILEVEL:
            entity_description = ZwaveMultilevelSensorEntityDescription(
                "multilevel", info=info
            )
        else:
            entity_description = ZwaveSensorBaseEntityDescription("sensor", info=info)

        if info.platform_hint == "string_sensor":
            entities.append(ZWaveStringSensor(config_entry, client, entity_description))
        elif info.platform_hint == "numeric_sensor":
            entities.append(
                ZWaveNumericSensor(config_entry, client, entity_description)
            )
        elif info.platform_hint == "list_sensor":
            entities.append(ZWaveListSensor(config_entry, client, entity_description))
        elif info.platform_hint == "config_parameter":
            entities.append(
                ZWaveConfigParameterSensor(config_entry, client, entity_description)
            )
        elif info.platform_hint == "meter":
            entities.append(ZWaveMeterSensor(config_entry, client, entity_description))
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
        entity_description: ZwaveSensorBaseEntityDescription,
    ) -> None:
        """Initialize a ZWaveSensorBase entity."""
        assert entity_description.info
        super().__init__(config_entry, client, entity_description.info)
        self.entity_description = entity_description

        # Entity class attributes
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
        if self.info.primary_value.metadata.unit is None:
            return None
        if self.info.primary_value.metadata.unit == "C":
            return TEMP_CELSIUS
        if self.info.primary_value.metadata.unit == "F":
            return TEMP_FAHRENHEIT

        return str(self.info.primary_value.metadata.unit)


class ZWaveMeterSensor(ZWaveNumericSensor):
    """Representation of a Z-Wave Meter CC sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        entity_description: ZwaveSensorBaseEntityDescription,
    ) -> None:
        """Initialize a ZWaveNumericSensor entity."""
        super().__init__(config_entry, client, entity_description)

        # Entity class attributes
        if self.device_class == DEVICE_CLASS_ENERGY:
            self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
        else:
            self._attr_state_class = STATE_CLASS_MEASUREMENT

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
        entity_description: ZwaveSensorBaseEntityDescription,
    ) -> None:
        """Initialize a ZWaveListSensor entity."""
        super().__init__(config_entry, client, entity_description)

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
        entity_description: ZwaveSensorBaseEntityDescription,
    ) -> None:
        """Initialize a ZWaveConfigParameterSensor entity."""
        super().__init__(config_entry, client, entity_description)
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
    _attr_entity_registry_enabled_default = False

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
        self._attr_device_info = {
            "identifiers": {get_device_id(self.client, self.node)},
        }
        self._attr_native_value: str = node.status.name.lower()

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        raise ValueError("There is no value to poll for this entity")

    def _status_changed(self, _: dict) -> None:
        """Call when status event is received."""
        self._attr_native_value = self.node.status.name.lower()
        self.async_write_ha_state()

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

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.client.connected and bool(self.node.ready)
