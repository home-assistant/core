"""Support for SolarEdge Modbus sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from solaredged import (
    Battery,
    BatteryStatus,
    Inverter,
    InverterStatus,
    Meter,
    SunSpecDID,
)

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import LOGGER
from .coordinator import SolarEdgeModbusConfigEntry
from .entity import (
    SolarEdgeModbusBatteryEntity,
    SolarEdgeModbusInverterEntity,
    SolarEdgeModbusMeterEntity,
)

PARALLEL_UPDATES = 0

# Per-phase points only carry data on split- and three-phase inverters.
_MULTI_PHASE = (SunSpecDID.SPLIT_PHASE_INVERTER, SunSpecDID.THREE_PHASE_INVERTER)

# Meters report per-phase points from two phases up; the third phase only on a
# three-phase meter, and line-to-neutral voltages on everything but a delta.
_MULTI_PHASE_METER = (
    SunSpecDID.SPLIT_PHASE_METER,
    SunSpecDID.THREE_PHASE_WYE_METER,
    SunSpecDID.THREE_PHASE_DELTA_METER,
)
_THREE_PHASE_METER = (
    SunSpecDID.THREE_PHASE_WYE_METER,
    SunSpecDID.THREE_PHASE_DELTA_METER,
)
# A delta meter has no neutral, so it measures nothing against one.
_NEUTRAL_METER = (
    SunSpecDID.SINGLE_PHASE_METER,
    SunSpecDID.SPLIT_PHASE_METER,
    SunSpecDID.THREE_PHASE_WYE_METER,
)
_PHASE_NEUTRAL_METER = (
    SunSpecDID.SPLIT_PHASE_METER,
    SunSpecDID.THREE_PHASE_WYE_METER,
)


@dataclass(frozen=True, kw_only=True)
class SolarEdgeModbusSensorEntityDescription[ComponentT](SensorEntityDescription):
    """Describes a SolarEdge Modbus sensor entity."""

    exists_fn: Callable[[ComponentT], bool] = lambda _: True
    value_fn: Callable[[ComponentT], StateType]


INVERTER_SENSORS: tuple[SolarEdgeModbusSensorEntityDescription[Inverter], ...] = (
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda inverter: inverter.ac_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda inverter: inverter.ac_energy,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda inverter: inverter.ac_current,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_a",
        translation_key="current_phase_a",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_current_a,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_b",
        translation_key="current_phase_b",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_current_b,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_c",
        translation_key="current_phase_c",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_current_c,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.SINGLE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_an,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_ab",
        translation_key="voltage_phase_ab",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_voltage_ab,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_bc",
        translation_key="voltage_phase_bc",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_bc,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_ca",
        translation_key="voltage_phase_ca",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_ca,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_an",
        translation_key="voltage_phase_an",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_voltage_an,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_bn",
        translation_key="voltage_phase_bn",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_voltage_bn,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_cn",
        translation_key="voltage_phase_cn",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_cn,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_power",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda inverter: inverter.dc_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_current",
        translation_key="dc_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda inverter: inverter.dc_current,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_voltage",
        translation_key="dc_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda inverter: inverter.dc_voltage,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda inverter: inverter.ac_frequency,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda inverter: inverter.temperature_heatsink,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda inverter: inverter.ac_va,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda inverter: inverter.ac_var,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda inverter: inverter.ac_power_factor,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="status",
        translation_key="inverter_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name.lower() for status in InverterStatus],
        value_fn=lambda inverter: (
            inverter.status.name.lower() if inverter.status is not None else None
        ),
    ),
)


METER_SENSORS: tuple[SolarEdgeModbusSensorEntityDescription[Meter], ...] = (
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda meter: meter.ac_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_exported",
        translation_key="energy_exported",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_exported,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_imported",
        translation_key="energy_imported",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_imported,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power_phase_a",
        translation_key="power_phase_a",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.ac_power_a,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power_phase_b",
        translation_key="power_phase_b",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.ac_power_b,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power_phase_c",
        translation_key="power_phase_c",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda meter: meter.did in _THREE_PHASE_METER,
        value_fn=lambda meter: meter.ac_power_c,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda meter: meter.ac_current,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_a",
        translation_key="current_phase_a",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.ac_current_a,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_b",
        translation_key="current_phase_b",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.ac_current_b,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_c",
        translation_key="current_phase_c",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda meter: meter.did in _THREE_PHASE_METER,
        value_fn=lambda meter: meter.ac_current_c,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda meter: meter.did in _NEUTRAL_METER,
        value_fn=lambda meter: meter.ac_voltage_ln,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_an",
        translation_key="voltage_phase_an",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda meter: meter.did in _PHASE_NEUTRAL_METER,
        value_fn=lambda meter: meter.ac_voltage_an,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_bn",
        translation_key="voltage_phase_bn",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda meter: meter.did in _PHASE_NEUTRAL_METER,
        value_fn=lambda meter: meter.ac_voltage_bn,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_cn",
        translation_key="voltage_phase_cn",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda meter: meter.did is SunSpecDID.THREE_PHASE_WYE_METER,
        value_fn=lambda meter: meter.ac_voltage_cn,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_ab",
        translation_key="voltage_phase_ab",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.ac_voltage_ab,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_bc",
        translation_key="voltage_phase_bc",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda meter: meter.did in _THREE_PHASE_METER,
        value_fn=lambda meter: meter.ac_voltage_bc,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_ca",
        translation_key="voltage_phase_ca",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda meter: meter.did in _THREE_PHASE_METER,
        value_fn=lambda meter: meter.ac_voltage_ca,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda meter: meter.ac_frequency,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda meter: meter.ac_va,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda meter: meter.ac_var,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda meter: meter.ac_power_factor,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_exported_phase_a",
        translation_key="energy_exported_phase_a",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.energy_exported_a,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_exported_phase_b",
        translation_key="energy_exported_phase_b",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.energy_exported_b,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_exported_phase_c",
        translation_key="energy_exported_phase_c",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        exists_fn=lambda meter: meter.did in _THREE_PHASE_METER,
        value_fn=lambda meter: meter.energy_exported_c,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_imported_phase_a",
        translation_key="energy_imported_phase_a",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.energy_imported_a,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_imported_phase_b",
        translation_key="energy_imported_phase_b",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        exists_fn=lambda meter: meter.did in _MULTI_PHASE_METER,
        value_fn=lambda meter: meter.energy_imported_b,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_imported_phase_c",
        translation_key="energy_imported_phase_c",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        exists_fn=lambda meter: meter.did in _THREE_PHASE_METER,
        value_fn=lambda meter: meter.energy_imported_c,
    ),
)


BATTERY_SENSORS: tuple[SolarEdgeModbusSensorEntityDescription[Battery], ...] = (
    SolarEdgeModbusSensorEntityDescription(
        key="dc_power",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda battery: battery.dc_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_exported",
        translation_key="energy_exported",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda battery: battery.energy_exported,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_imported",
        translation_key="energy_imported",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda battery: battery.energy_imported,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="state_of_energy",
        translation_key="state_of_energy",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda battery: battery.state_of_energy,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="state_of_health",
        translation_key="state_of_health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda battery: battery.state_of_health,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda battery: battery.temperature_average,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_available",
        translation_key="energy_available",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda battery: battery.energy_available,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="energy_max",
        translation_key="energy_max",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda battery: battery.energy_max,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="rated_energy",
        translation_key="rated_energy",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda battery: battery.rated_energy,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_voltage",
        translation_key="dc_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda battery: battery.dc_voltage,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_current",
        translation_key="dc_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda battery: battery.dc_current,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="max_charge_power",
        translation_key="max_charge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda battery: battery.max_charge_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="max_discharge_power",
        translation_key="max_discharge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda battery: battery.max_discharge_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="max_charge_peak_power",
        translation_key="max_charge_peak_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda battery: battery.max_charge_peak_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="max_discharge_peak_power",
        translation_key="max_discharge_peak_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda battery: battery.max_discharge_peak_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="temperature_max",
        translation_key="temperature_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda battery: battery.temperature_max,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="status",
        translation_key="battery_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name.lower() for status in BatteryStatus],
        value_fn=lambda battery: (
            battery.status.name.lower() if battery.status is not None else None
        ),
    ),
)


def _inverter_sensor(
    entry: SolarEdgeModbusConfigEntry,
    description: SolarEdgeModbusSensorEntityDescription[Inverter],
) -> SensorEntity:
    """Build an inverter sensor, monotonic where its state class asks for it."""
    if description.state_class is SensorStateClass.TOTAL_INCREASING:
        return SolarEdgeModbusInverterEnergySensorEntity(
            entry=entry, description=description
        )
    return SolarEdgeModbusInverterSensorEntity(entry=entry, description=description)


def _meter_sensor(
    entry: SolarEdgeModbusConfigEntry,
    description: SolarEdgeModbusSensorEntityDescription[Meter],
    index: int,
) -> SensorEntity:
    """Build a meter sensor, monotonic where its state class asks for it."""
    if description.state_class is SensorStateClass.TOTAL_INCREASING:
        return SolarEdgeModbusMeterEnergySensorEntity(
            entry=entry, description=description, index=index
        )
    return SolarEdgeModbusMeterSensorEntity(
        entry=entry, description=description, index=index
    )


def _battery_sensor(
    entry: SolarEdgeModbusConfigEntry,
    description: SolarEdgeModbusSensorEntityDescription[Battery],
    index: int,
) -> SensorEntity:
    """Build a battery sensor, monotonic where its state class asks for it."""
    if description.state_class is SensorStateClass.TOTAL_INCREASING:
        return SolarEdgeModbusBatteryEnergySensorEntity(
            entry=entry, description=description, index=index
        )
    return SolarEdgeModbusBatterySensorEntity(
        entry=entry, description=description, index=index
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SolarEdge Modbus sensor entities based on a config entry."""
    solaredge = entry.runtime_data.solaredge

    entities: list[SensorEntity] = [
        _inverter_sensor(entry, description)
        for description in INVERTER_SENSORS
        if description.exists_fn(solaredge.inverter)
    ]
    entities.extend(
        _meter_sensor(entry, description, index)
        for index, meter in enumerate(solaredge.meters, 1)
        for description in METER_SENSORS
        if description.exists_fn(meter)
    )
    entities.extend(
        _battery_sensor(entry, description, index)
        for index, battery in enumerate(solaredge.batteries, 1)
        for description in BATTERY_SENSORS
        if description.exists_fn(battery)
    )

    async_add_entities(entities)


class SolarEdgeModbusInverterSensorEntity(SolarEdgeModbusInverterEntity, SensorEntity):
    """Defines a SolarEdge Modbus inverter sensor entity."""

    entity_description: SolarEdgeModbusSensorEntityDescription[Inverter]

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.solaredge.inverter)


class SolarEdgeModbusMeterSensorEntity(SolarEdgeModbusMeterEntity, SensorEntity):
    """Defines a SolarEdge Modbus meter sensor entity."""

    entity_description: SolarEdgeModbusSensorEntityDescription[Meter]

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.solaredge.meters[self._index - 1]
        )


class SolarEdgeModbusEnergySensorEntity(RestoreSensor):
    """Keeps a lifetime-energy sensor monotonic across glitches and restarts.

    SolarEdge accumulators transiently report lower values (or zero) around
    the inverter's sleep/wake transition; a single such sample fed to a
    ``total_increasing`` sensor registers as a meter reset and corrupts the
    long-term statistics. The highest value seen wins, and it is restored
    across restarts so an overnight restart does not lose that truth.
    """

    _highest_value: float | None = None
    _glitch_logged = False

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the highest previously seen value."""
        await super().async_added_to_hass()

        data = await self.async_get_last_sensor_data()
        if data is not None and isinstance(data.native_value, (int, float)):
            self._highest_value = data.native_value

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value, never lower than seen before."""
        value = super().native_value
        if not isinstance(value, (int, float)):
            return self._highest_value

        if self._highest_value is None or value >= self._highest_value:
            self._highest_value = value
            self._glitch_logged = False
            return value

        if not self._glitch_logged:
            LOGGER.warning(
                (
                    "%s reported a lifetime energy of %s Wh, lower than the"
                    " %s Wh seen before; ignoring the lower value (a known"
                    " SolarEdge glitch around its sleep/wake transition)"
                ),
                self.entity_id,
                value,
                self._highest_value,
            )
            self._glitch_logged = True

        return self._highest_value


class SolarEdgeModbusInverterEnergySensorEntity(
    SolarEdgeModbusEnergySensorEntity, SolarEdgeModbusInverterSensorEntity
):
    """Defines a monotonic SolarEdge Modbus inverter energy sensor entity."""


class SolarEdgeModbusMeterEnergySensorEntity(
    SolarEdgeModbusEnergySensorEntity, SolarEdgeModbusMeterSensorEntity
):
    """Defines a monotonic SolarEdge Modbus meter energy sensor entity."""


class SolarEdgeModbusBatterySensorEntity(SolarEdgeModbusBatteryEntity, SensorEntity):
    """Defines a SolarEdge Modbus battery sensor entity."""

    entity_description: SolarEdgeModbusSensorEntityDescription[Battery]

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.solaredge.batteries[self._index - 1]
        )


class SolarEdgeModbusBatteryEnergySensorEntity(
    SolarEdgeModbusEnergySensorEntity, SolarEdgeModbusBatterySensorEntity
):
    """Defines a monotonic SolarEdge Modbus battery energy sensor entity."""
