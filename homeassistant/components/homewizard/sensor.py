"""Creates HomeWizard sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homewizard_energy.models import Data, ExternalDevice

from homeassistant.components.sensor import (
    DEVICE_CLASS_UNITS,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_VIA_DEVICE,
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HomeWizardConfigEntry
from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HomeWizardSensorEntityDescription(SensorEntityDescription):
    """Class describing HomeWizard sensor entities."""

    enabled_fn: Callable[[Data], bool] = lambda data: True
    has_fn: Callable[[Data], bool]
    value_fn: Callable[[Data], StateType]


@dataclass(frozen=True, kw_only=True)
class HomeWizardExternalSensorEntityDescription(SensorEntityDescription):
    """Class describing HomeWizard sensor entities."""

    suggested_device_class: SensorDeviceClass
    device_name: str


def to_percentage(value: float | None) -> float | None:
    """Convert 0..1 value to percentage when value is not None."""
    return value * 100 if value is not None else None


SENSORS: Final[tuple[HomeWizardSensorEntityDescription, ...]] = (
    HomeWizardSensorEntityDescription(
        key="smr_version",
        translation_key="dsmr_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.smr_version is not None,
        value_fn=lambda data: data.smr_version,
    ),
    HomeWizardSensorEntityDescription(
        key="meter_model",
        translation_key="meter_model",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.meter_model is not None,
        value_fn=lambda data: data.meter_model,
    ),
    HomeWizardSensorEntityDescription(
        key="unique_meter_id",
        translation_key="unique_meter_id",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.unique_meter_id is not None,
        value_fn=lambda data: data.unique_meter_id,
    ),
    HomeWizardSensorEntityDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.wifi_ssid is not None,
        value_fn=lambda data: data.wifi_ssid,
    ),
    HomeWizardSensorEntityDescription(
        key="active_tariff",
        translation_key="active_tariff",
        has_fn=lambda data: data.active_tariff is not None,
        value_fn=lambda data: (
            None if data.active_tariff is None else str(data.active_tariff)
        ),
        device_class=SensorDeviceClass.ENUM,
        options=["1", "2", "3", "4"],
    ),
    HomeWizardSensorEntityDescription(
        key="wifi_strength",
        translation_key="wifi_strength",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.wifi_strength is not None,
        value_fn=lambda data: data.wifi_strength,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_kwh",
        translation_key="total_energy_import_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_kwh is not None,
        value_fn=lambda data: data.total_energy_import_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t1_kwh",
        translation_key="total_energy_import_tariff_kwh",
        translation_placeholders={"tariff": "1"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: (
            # SKT/SDM230/630 provides both total and tariff 1: duplicate.
            data.total_energy_import_t1_kwh is not None
            and data.total_energy_export_t2_kwh is not None
        ),
        value_fn=lambda data: data.total_energy_import_t1_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t2_kwh",
        translation_key="total_energy_import_tariff_kwh",
        translation_placeholders={"tariff": "2"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_t2_kwh is not None,
        value_fn=lambda data: data.total_energy_import_t2_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t3_kwh",
        translation_key="total_energy_import_tariff_kwh",
        translation_placeholders={"tariff": "3"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_t3_kwh is not None,
        value_fn=lambda data: data.total_energy_import_t3_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t4_kwh",
        translation_key="total_energy_import_tariff_kwh",
        translation_placeholders={"tariff": "4"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_t4_kwh is not None,
        value_fn=lambda data: data.total_energy_import_t4_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_kwh",
        translation_key="total_energy_export_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_kwh != 0,
        value_fn=lambda data: data.total_energy_export_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t1_kwh",
        translation_key="total_energy_export_tariff_kwh",
        translation_placeholders={"tariff": "1"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: (
            # SKT/SDM230/630 provides both total and tariff 1: duplicate.
            data.total_energy_export_t1_kwh is not None
            and data.total_energy_export_t2_kwh is not None
        ),
        enabled_fn=lambda data: data.total_energy_export_t1_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t1_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t2_kwh",
        translation_key="total_energy_export_tariff_kwh",
        translation_placeholders={"tariff": "2"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_t2_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_t2_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t2_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t3_kwh",
        translation_key="total_energy_export_tariff_kwh",
        translation_placeholders={"tariff": "3"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_t3_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_t3_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t3_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t4_kwh",
        translation_key="total_energy_export_tariff_kwh",
        translation_placeholders={"tariff": "4"},
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_t4_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_t4_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t4_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_w is not None,
        value_fn=lambda data: data.active_power_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l1_w",
        translation_key="active_power_phase_w",
        translation_placeholders={"phase": "1"},
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_l1_w is not None,
        value_fn=lambda data: data.active_power_l1_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l2_w",
        translation_key="active_power_phase_w",
        translation_placeholders={"phase": "2"},
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_l2_w is not None,
        value_fn=lambda data: data.active_power_l2_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l3_w",
        translation_key="active_power_phase_w",
        translation_placeholders={"phase": "3"},
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_l3_w is not None,
        value_fn=lambda data: data.active_power_l3_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_voltage_v is not None,
        value_fn=lambda data: data.active_voltage_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l1_v",
        translation_key="active_voltage_phase_v",
        translation_placeholders={"phase": "1"},
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_voltage_l1_v is not None,
        value_fn=lambda data: data.active_voltage_l1_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l2_v",
        translation_key="active_voltage_phase_v",
        translation_placeholders={"phase": "2"},
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_voltage_l2_v is not None,
        value_fn=lambda data: data.active_voltage_l2_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l3_v",
        translation_key="active_voltage_phase_v",
        translation_placeholders={"phase": "3"},
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_voltage_l3_v is not None,
        value_fn=lambda data: data.active_voltage_l3_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_current_a is not None,
        value_fn=lambda data: data.active_current_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l1_a",
        translation_key="active_current_phase_a",
        translation_placeholders={"phase": "1"},
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_current_l1_a is not None,
        value_fn=lambda data: data.active_current_l1_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l2_a",
        translation_key="active_current_phase_a",
        translation_placeholders={"phase": "2"},
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_current_l2_a is not None,
        value_fn=lambda data: data.active_current_l2_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l3_a",
        translation_key="active_current_phase_a",
        translation_placeholders={"phase": "3"},
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_current_l3_a is not None,
        value_fn=lambda data: data.active_current_l3_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_frequency_hz",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_frequency_hz is not None,
        value_fn=lambda data: data.active_frequency_hz,
    ),
    HomeWizardSensorEntityDescription(
        key="active_apparent_power_va",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_apparent_power_va is not None,
        value_fn=lambda data: data.active_apparent_power_va,
    ),
    HomeWizardSensorEntityDescription(
        key="active_apparent_power_l1_va",
        translation_key="active_apparent_power_phase_va",
        translation_placeholders={"phase": "1"},
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_apparent_power_l1_va is not None,
        value_fn=lambda data: data.active_apparent_power_l1_va,
    ),
    HomeWizardSensorEntityDescription(
        key="active_apparent_power_l2_va",
        translation_key="active_apparent_power_phase_va",
        translation_placeholders={"phase": "2"},
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_apparent_power_l2_va is not None,
        value_fn=lambda data: data.active_apparent_power_l2_va,
    ),
    HomeWizardSensorEntityDescription(
        key="active_apparent_power_l3_va",
        translation_key="active_apparent_power_phase_va",
        translation_placeholders={"phase": "3"},
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_apparent_power_l3_va is not None,
        value_fn=lambda data: data.active_apparent_power_l3_va,
    ),
    HomeWizardSensorEntityDescription(
        key="active_reactive_power_var",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_reactive_power_var is not None,
        value_fn=lambda data: data.active_reactive_power_var,
    ),
    HomeWizardSensorEntityDescription(
        key="active_reactive_power_l1_var",
        translation_key="active_reactive_power_phase_var",
        translation_placeholders={"phase": "1"},
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_reactive_power_l1_var is not None,
        value_fn=lambda data: data.active_reactive_power_l1_var,
    ),
    HomeWizardSensorEntityDescription(
        key="active_reactive_power_l2_var",
        translation_key="active_reactive_power_phase_var",
        translation_placeholders={"phase": "2"},
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_reactive_power_l2_var is not None,
        value_fn=lambda data: data.active_reactive_power_l2_var,
    ),
    HomeWizardSensorEntityDescription(
        key="active_reactive_power_l3_var",
        translation_key="active_reactive_power_phase_var",
        translation_placeholders={"phase": "3"},
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_reactive_power_l3_var is not None,
        value_fn=lambda data: data.active_reactive_power_l3_var,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_factor",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_power_factor is not None,
        value_fn=lambda data: to_percentage(data.active_power_factor),
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_factor_l1",
        translation_key="active_power_factor_phase",
        translation_placeholders={"phase": "1"},
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_power_factor_l1 is not None,
        value_fn=lambda data: to_percentage(data.active_power_factor_l1),
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_factor_l2",
        translation_key="active_power_factor_phase",
        translation_placeholders={"phase": "2"},
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_power_factor_l2 is not None,
        value_fn=lambda data: to_percentage(data.active_power_factor_l2),
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_factor_l3",
        translation_key="active_power_factor_phase",
        translation_placeholders={"phase": "3"},
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_power_factor_l3 is not None,
        value_fn=lambda data: to_percentage(data.active_power_factor_l3),
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l1_count",
        translation_key="voltage_sag_phase_count",
        translation_placeholders={"phase": "1"},
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_sag_l1_count is not None,
        value_fn=lambda data: data.voltage_sag_l1_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l2_count",
        translation_key="voltage_sag_phase_count",
        translation_placeholders={"phase": "2"},
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_sag_l2_count is not None,
        value_fn=lambda data: data.voltage_sag_l2_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l3_count",
        translation_key="voltage_sag_phase_count",
        translation_placeholders={"phase": "3"},
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_sag_l3_count is not None,
        value_fn=lambda data: data.voltage_sag_l3_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l1_count",
        translation_key="voltage_swell_phase_count",
        translation_placeholders={"phase": "1"},
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_swell_l1_count is not None,
        value_fn=lambda data: data.voltage_swell_l1_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l2_count",
        translation_key="voltage_swell_phase_count",
        translation_placeholders={"phase": "2"},
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_swell_l2_count is not None,
        value_fn=lambda data: data.voltage_swell_l2_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l3_count",
        translation_key="voltage_swell_phase_count",
        translation_placeholders={"phase": "3"},
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_swell_l3_count is not None,
        value_fn=lambda data: data.voltage_swell_l3_count,
    ),
    HomeWizardSensorEntityDescription(
        key="any_power_fail_count",
        translation_key="any_power_fail_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.any_power_fail_count is not None,
        value_fn=lambda data: data.any_power_fail_count,
    ),
    HomeWizardSensorEntityDescription(
        key="long_power_fail_count",
        translation_key="long_power_fail_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.long_power_fail_count is not None,
        value_fn=lambda data: data.long_power_fail_count,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_average_w",
        translation_key="active_power_average_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        has_fn=lambda data: data.active_power_average_w is not None,
        value_fn=lambda data: data.active_power_average_w,
    ),
    HomeWizardSensorEntityDescription(
        key="monthly_power_peak_w",
        translation_key="monthly_power_peak_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        has_fn=lambda data: data.monthly_power_peak_w is not None,
        value_fn=lambda data: data.monthly_power_peak_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_liter_lpm",
        translation_key="active_liter_lpm",
        native_unit_of_measurement="l/min",
        state_class=SensorStateClass.MEASUREMENT,
        has_fn=lambda data: data.active_liter_lpm is not None,
        value_fn=lambda data: data.active_liter_lpm,
    ),
    HomeWizardSensorEntityDescription(
        key="total_liter_m3",
        translation_key="total_liter_m3",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_liter_m3 is not None,
        value_fn=lambda data: data.total_liter_m3,
    ),
)


EXTERNAL_SENSORS = {
    ExternalDevice.DeviceType.GAS_METER: HomeWizardExternalSensorEntityDescription(
        key="gas_meter",
        suggested_device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_name="Gas meter",
    ),
    ExternalDevice.DeviceType.HEAT_METER: HomeWizardExternalSensorEntityDescription(
        key="heat_meter",
        suggested_device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_name="Heat meter",
    ),
    ExternalDevice.DeviceType.WARM_WATER_METER: HomeWizardExternalSensorEntityDescription(
        key="warm_water_meter",
        suggested_device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_name="Warm water meter",
    ),
    ExternalDevice.DeviceType.WATER_METER: HomeWizardExternalSensorEntityDescription(
        key="water_meter",
        suggested_device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_name="Water meter",
    ),
    ExternalDevice.DeviceType.INLET_HEAT_METER: HomeWizardExternalSensorEntityDescription(
        key="inlet_heat_meter",
        suggested_device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_name="Inlet heat meter",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeWizardConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize sensors."""

    data = entry.runtime_data.data.data

    # Initialize default sensors
    entities: list = [
        HomeWizardSensorEntity(entry.runtime_data, description)
        for description in SENSORS
        if description.has_fn(data)
    ]

    # Initialize external devices
    if data.external_devices is not None:
        for unique_id, device in data.external_devices.items():
            if description := EXTERNAL_SENSORS.get(device.meter_type):
                # Add external device
                entities.append(
                    HomeWizardExternalSensorEntity(
                        entry.runtime_data, description, unique_id
                    )
                )

    async_add_entities(entities)


class HomeWizardSensorEntity(HomeWizardEntity, SensorEntity):
    """Representation of a HomeWizard Sensor."""

    entity_description: HomeWizardSensorEntityDescription

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        description: HomeWizardSensorEntityDescription,
    ) -> None:
        """Initialize Sensor Domain."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        if not description.enabled_fn(self.coordinator.data.data):
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data.data)

    @property
    def available(self) -> bool:
        """Return availability of meter."""
        return super().available and self.native_value is not None


class HomeWizardExternalSensorEntity(HomeWizardEntity, SensorEntity):
    """Representation of externally connected HomeWizard Sensor."""

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        description: HomeWizardExternalSensorEntityDescription,
        device_unique_id: str,
    ) -> None:
        """Initialize Externally connected HomeWizard Sensors."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_unique_id
        self._suggested_device_class = description.suggested_device_class
        self._attr_unique_id = f"{DOMAIN}_{device_unique_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            name=description.device_name,
            manufacturer="HomeWizard",
            model=coordinator.data.device.product_type,
            serial_number=device_unique_id,
        )
        if coordinator.data.device.serial is not None:
            self._attr_device_info[ATTR_VIA_DEVICE] = (
                DOMAIN,
                coordinator.data.device.serial,
            )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the sensor value."""
        return self.device.value if self.device is not None else None

    @property
    def device(self) -> ExternalDevice | None:
        """Return ExternalDevice object."""
        return (
            self.coordinator.data.data.external_devices[self._device_id]
            if self.coordinator.data.data.external_devices is not None
            else None
        )

    @property
    def available(self) -> bool:
        """Return availability of meter."""
        return super().available and self.device is not None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement based on device unit."""
        if (device := self.device) is None:
            return None

        # API returns 'm3' but we expect m³
        if device.unit == "m3":
            return UnitOfVolume.CUBIC_METERS

        return device.unit

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Validate unit of measurement and set device class."""
        if (
            self.native_unit_of_measurement
            not in DEVICE_CLASS_UNITS[self._suggested_device_class]
        ):
            return None

        return self._suggested_device_class
