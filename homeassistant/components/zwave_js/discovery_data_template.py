"""Data template classes for discovery used to generate additional data for setup."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.meter import (
    CURRENT_METER_TYPES,
    ENERGY_TOTAL_INCREASING_METER_TYPES,
    POWER_FACTOR_METER_TYPES,
    POWER_METER_TYPES,
    VOLTAGE_METER_TYPES,
    ElectricScale,
    MeterScaleType,
)
from zwave_js_server.const.command_class.multilevel_sensor import (
    CO2_SENSORS,
    CO_SENSORS,
    CURRENT_SENSORS,
    ENERGY_MEASUREMENT_SENSORS,
    HUMIDITY_SENSORS,
    ILLUMINANCE_SENSORS,
    POWER_SENSORS,
    PRESSURE_SENSORS,
    SIGNAL_STRENGTH_SENSORS,
    TEMPERATURE_SENSORS,
    TIMESTAMP_SENSORS,
    VOLTAGE_SENSORS,
    MultilevelSensorType,
)
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue, get_value_id
from zwave_js_server.util.command_class.meter import get_meter_scale_type
from zwave_js_server.util.command_class.multilevel_sensor import (
    get_multilevel_sensor_type,
)

from .const import (
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
    ENTITY_DESC_KEY_TIMESTAMP,
    ENTITY_DESC_KEY_TOTAL_INCREASING,
    ENTITY_DESC_KEY_VOLTAGE,
)

METER_DEVICE_CLASS_MAP: dict[str, set[MeterScaleType]] = {
    ENTITY_DESC_KEY_CURRENT: CURRENT_METER_TYPES,
    ENTITY_DESC_KEY_VOLTAGE: VOLTAGE_METER_TYPES,
    ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING: ENERGY_TOTAL_INCREASING_METER_TYPES,
    ENTITY_DESC_KEY_POWER: POWER_METER_TYPES,
    ENTITY_DESC_KEY_POWER_FACTOR: POWER_FACTOR_METER_TYPES,
}

MULTILEVEL_SENSOR_DEVICE_CLASS_MAP: dict[str, set[MultilevelSensorType]] = {
    ENTITY_DESC_KEY_CO: CO_SENSORS,
    ENTITY_DESC_KEY_CO2: CO2_SENSORS,
    ENTITY_DESC_KEY_CURRENT: CURRENT_SENSORS,
    ENTITY_DESC_KEY_ENERGY_MEASUREMENT: ENERGY_MEASUREMENT_SENSORS,
    ENTITY_DESC_KEY_HUMIDITY: HUMIDITY_SENSORS,
    ENTITY_DESC_KEY_ILLUMINANCE: ILLUMINANCE_SENSORS,
    ENTITY_DESC_KEY_POWER: POWER_SENSORS,
    ENTITY_DESC_KEY_PRESSURE: PRESSURE_SENSORS,
    ENTITY_DESC_KEY_SIGNAL_STRENGTH: SIGNAL_STRENGTH_SENSORS,
    ENTITY_DESC_KEY_TEMPERATURE: TEMPERATURE_SENSORS,
    ENTITY_DESC_KEY_TIMESTAMP: TIMESTAMP_SENSORS,
    ENTITY_DESC_KEY_VOLTAGE: VOLTAGE_SENSORS,
}


@dataclass
class ZwaveValueID:
    """Class to represent a value ID."""

    property_: str | int
    command_class: int
    endpoint: int | None = None
    property_key: str | int | None = None


@dataclass
class BaseDiscoverySchemaDataTemplate:
    """Base class for discovery schema data templates."""

    static_data: Any | None = None

    def resolve_data(self, value: ZwaveValue) -> Any:
        """
        Resolve helper class data for a discovered value.

        Can optionally be implemented by subclasses if input data needs to be
        transformed once discovered Value is available.
        """
        # pylint: disable=no-self-use
        return {}

    def values_to_watch(self, resolved_data: Any) -> Iterable[ZwaveValue]:
        """
        Return list of all ZwaveValues resolved by helper that should be watched.

        Should be implemented by subclasses only if there are values to watch.
        """
        # pylint: disable=no-self-use
        return []

    def value_ids_to_watch(self, resolved_data: Any) -> set[str]:
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

    lookup_table: dict[str | int, ZwaveValueID] = field(default_factory=dict)
    dependent_value: ZwaveValueID | None = None

    def resolve_data(self, value: ZwaveValue) -> dict[str, Any]:
        """Resolve helper class data for a discovered value."""
        if not self.lookup_table or not self.dependent_value:
            raise ValueError("Invalid discovery data template")
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

    def resolve_data(self, value: ZwaveValue) -> str | None:
        """Resolve helper class data for a discovered value."""

        if value.command_class == CommandClass.BATTERY:
            return ENTITY_DESC_KEY_BATTERY

        if value.command_class == CommandClass.METER:
            scale_type = get_meter_scale_type(value)
            # We do this because even though these are energy scales, they don't meet
            # the unit requirements for the energy device class.
            if scale_type in (
                ElectricScale.PULSE_COUNT,
                ElectricScale.KILOVOLT_AMPERE_HOUR,
                ElectricScale.KILOVOLT_AMPERE_REACTIVE_HOUR,
            ):
                return ENTITY_DESC_KEY_TOTAL_INCREASING
            # We do this because even though these are power scales, they don't meet
            # the unit requirements for the power device class.
            if scale_type == ElectricScale.KILOVOLT_AMPERE_REACTIVE:
                return ENTITY_DESC_KEY_MEASUREMENT

            for key, scale_type_set in METER_DEVICE_CLASS_MAP.items():
                if scale_type in scale_type_set:
                    return key

        if value.command_class == CommandClass.SENSOR_MULTILEVEL:
            sensor_type = get_multilevel_sensor_type(value)
            if sensor_type == MultilevelSensorType.TARGET_TEMPERATURE:
                return ENTITY_DESC_KEY_TARGET_TEMPERATURE
            for (
                key,
                sensor_type_set,
            ) in MULTILEVEL_SENSOR_DEVICE_CLASS_MAP.items():
                if sensor_type in sensor_type_set:
                    return key

        return None
