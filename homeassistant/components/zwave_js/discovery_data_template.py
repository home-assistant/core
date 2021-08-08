"""Data template classes for discovery used to generate additional data for setup."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

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
    SIGNAL_STRENGTH_SENSORS,
    TEMPERATURE_SENSORS,
    TIMESTAMP_SENSORS,
    VOLTAGE_METER_TYPES,
    VOLTAGE_SENSORS,
    CommandClass,
    MeterType,
    MultilevelSensorType,
)
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue, get_value_id

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
)

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
class ZwaveValueID:
    """Class to represent a value ID."""

    property_: str | int
    command_class: int
    endpoint: int | None = None
    property_key: str | int | None = None


class BaseDiscoverySchemaDataTemplate:
    """Base class for discovery schema data templates."""

    def resolve_data(self, value: ZwaveValue) -> dict[str, Any]:
        """
        Resolve helper class data for a discovered value.

        Can optionally be implemented by subclasses if input data needs to be
        transformed once discovered Value is available.
        """
        # pylint: disable=no-self-use
        return {}

    def values_to_watch(self, resolved_data: dict[str, Any]) -> Iterable[ZwaveValue]:
        """
        Return list of all ZwaveValues resolved by helper that should be watched.

        Should be implemented by subclasses only if there are values to watch.
        """
        # pylint: disable=no-self-use
        return []

    def value_ids_to_watch(self, resolved_data: dict[str, Any]) -> set[str]:
        """
        Return list of all Value IDs resolved by helper that should be watched.

        Not to be overwritten by subclasses.
        """
        return {val.value_id for val in self.values_to_watch(resolved_data) if val}

    @staticmethod
    def _get_value_from_id(
        node: ZwaveNode, value_id_obj: ZwaveValueID
    ) -> ZwaveValue | None:
        """Get a ZwaveValue from a node using a ZwaveValueDict."""
        value_id = get_value_id(
            node,
            value_id_obj.command_class,
            value_id_obj.property_,
            endpoint=value_id_obj.endpoint,
            property_key=value_id_obj.property_key,
        )
        return node.values.get(value_id)


@dataclass
class DynamicCurrentTempClimateDataTemplate(BaseDiscoverySchemaDataTemplate):
    """Data template class for Z-Wave JS Climate entities with dynamic current temps."""

    lookup_table: dict[str | int, ZwaveValueID]
    dependent_value: ZwaveValueID

    def resolve_data(self, value: ZwaveValue) -> dict[str, Any]:
        """Resolve helper class data for a discovered value."""
        data: dict[str, Any] = {
            "lookup_table": {},
            "dependent_value": self._get_value_from_id(
                value.node, self.dependent_value
            ),
        }
        for key in self.lookup_table:
            data["lookup_table"][key] = self._get_value_from_id(
                value.node, self.lookup_table[key]
            )

        return data

    def values_to_watch(self, resolved_data: dict[str, Any]) -> Iterable[ZwaveValue]:
        """Return list of all ZwaveValues resolved by helper that should be watched."""
        return [
            *resolved_data["lookup_table"].values(),
            resolved_data["dependent_value"],
        ]

    @staticmethod
    def current_temperature_value(resolved_data: dict[str, Any]) -> ZwaveValue | None:
        """Get current temperature ZwaveValue from resolved data."""
        lookup_table: dict[str | int, ZwaveValue | None] = resolved_data["lookup_table"]
        dependent_value: ZwaveValue | None = resolved_data["dependent_value"]

        if dependent_value and dependent_value.value is not None:
            lookup_key = dependent_value.metadata.states[
                str(dependent_value.value)
            ].split("-")[0]
            return lookup_table.get(lookup_key)

        return None


class NumericSensorDataTemplate(BaseDiscoverySchemaDataTemplate):
    """Data template class for Z-Wave Sensor entities."""

    def resolve_data(self, value: ZwaveValue) -> dict[str, Any]:
        """Resolve helper class data for a discovered value."""
        data = {}
        if value.command_class == CommandClass.BATTERY:
            data["device_class"] = DEVICE_CLASS_BATTERY
            data["state_class"] = STATE_CLASS_MEASUREMENT
        elif value.command_class == CommandClass.METER:
            data["state_class"] = STATE_CLASS_MEASUREMENT
            cc_specific = value.metadata.cc_specific
            meter_type_id = cc_specific[CC_SPECIFIC_METER_TYPE]
            scale_type_id = cc_specific[CC_SPECIFIC_SCALE]
            try:
                meter_type = MeterType(meter_type_id)
            except ValueError:
                return data
            scale_enum = METER_TYPE_TO_SCALE_ENUM_MAP[meter_type]
            try:
                scale_type = scale_enum(scale_type_id)
            except ValueError:
                return data
            for device_class, scale_type_set in METER_DEVICE_CLASS_MAP.items():
                if scale_type in scale_type_set:
                    data["device_class"] = device_class
                    break
        elif value.command_class == CommandClass.SENSOR_MULTILEVEL:
            cc_specific = value.metadata.cc_specific
            sensor_type_id = cc_specific[CC_SPECIFIC_SENSOR_TYPE]
            try:
                sensor_type = MultilevelSensorType(sensor_type_id)
            except ValueError:
                return data
            for (
                device_class,
                sensor_type_set,
            ) in MULTILEVEL_SENSOR_DEVICE_CLASS_MAP.items():
                if sensor_type in sensor_type_set:
                    data["device_class"] = device_class
                    break
            if sensor_type != MultilevelSensorType.TARGET_TEMPERATURE:
                data["state_class"] = STATE_CLASS_MEASUREMENT

        return data
