"""Creates HomeWizard sensor entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homewizard_energy.models import Data

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity

PARALLEL_UPDATES = 1


@dataclass
class HomeWizardEntityDescriptionMixin:
    """Mixin values for HomeWizard entities."""

    has_fn: Callable[[Data], bool]
    value_fn: Callable[[Data], StateType]


@dataclass
class HomeWizardSensorEntityDescription(
    SensorEntityDescription, HomeWizardEntityDescriptionMixin
):
    """Class describing HomeWizard sensor entities."""

    enabled_fn: Callable[[Data], bool] = lambda data: True


SENSORS: Final[tuple[HomeWizardSensorEntityDescription, ...]] = (
    HomeWizardSensorEntityDescription(
        key="smr_version",
        translation_key="dsmr_version",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.smr_version is not None,
        value_fn=lambda data: data.smr_version,
    ),
    HomeWizardSensorEntityDescription(
        key="meter_model",
        translation_key="meter_model",
        icon="mdi:gauge",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.meter_model is not None,
        value_fn=lambda data: data.meter_model,
    ),
    HomeWizardSensorEntityDescription(
        key="unique_meter_id",
        translation_key="unique_meter_id",
        icon="mdi:alphabetical-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.unique_meter_id is not None,
        value_fn=lambda data: data.unique_meter_id,
    ),
    HomeWizardSensorEntityDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.wifi_ssid is not None,
        value_fn=lambda data: data.wifi_ssid,
    ),
    HomeWizardSensorEntityDescription(
        key="active_tariff",
        translation_key="active_tariff",
        icon="mdi:calendar-clock",
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
        icon="mdi:wifi",
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
        value_fn=lambda data: data.total_energy_import_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t1_kwh",
        translation_key="total_energy_import_t1_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_t1_kwh is not None,
        value_fn=lambda data: data.total_energy_import_t1_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t2_kwh",
        translation_key="total_energy_import_t2_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_t2_kwh is not None,
        value_fn=lambda data: data.total_energy_import_t2_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t3_kwh",
        translation_key="total_energy_import_t3_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_t3_kwh is not None,
        value_fn=lambda data: data.total_energy_import_t3_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t4_kwh",
        translation_key="total_energy_import_t4_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_import_t4_kwh is not None,
        value_fn=lambda data: data.total_energy_import_t4_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_kwh",
        translation_key="total_energy_export_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_kwh != 0,
        value_fn=lambda data: data.total_energy_export_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t1_kwh",
        translation_key="total_energy_export_t1_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_t1_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_t1_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t1_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t2_kwh",
        translation_key="total_energy_export_t2_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_t2_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_t2_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t2_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t3_kwh",
        translation_key="total_energy_export_t3_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_t3_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_t3_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t3_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t4_kwh",
        translation_key="total_energy_export_t4_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_energy_export_t4_kwh is not None,
        enabled_fn=lambda data: data.total_energy_export_t4_kwh != 0,
        value_fn=lambda data: data.total_energy_export_t4_kwh or None,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_w",
        translation_key="active_power_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_w is not None,
        value_fn=lambda data: data.active_power_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l1_w",
        translation_key="active_power_l1_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_l1_w is not None,
        value_fn=lambda data: data.active_power_l1_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l2_w",
        translation_key="active_power_l2_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_l2_w is not None,
        value_fn=lambda data: data.active_power_l2_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l3_w",
        translation_key="active_power_l3_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: data.active_power_l3_w is not None,
        value_fn=lambda data: data.active_power_l3_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l1_v",
        translation_key="active_voltage_l1_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_voltage_l1_v is not None,
        value_fn=lambda data: data.active_voltage_l1_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l2_v",
        translation_key="active_voltage_l2_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_voltage_l2_v is not None,
        value_fn=lambda data: data.active_voltage_l2_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l3_v",
        translation_key="active_voltage_l3_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_voltage_l3_v is not None,
        value_fn=lambda data: data.active_voltage_l3_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l1_a",
        translation_key="active_current_l1_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_current_l1_a is not None,
        value_fn=lambda data: data.active_current_l1_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l2_a",
        translation_key="active_current_l2_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_current_l2_a is not None,
        value_fn=lambda data: data.active_current_l2_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l3_a",
        translation_key="active_current_l3_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_current_l3_a is not None,
        value_fn=lambda data: data.active_current_l3_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_frequency_hz",
        translation_key="active_frequency_hz",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.active_frequency_hz is not None,
        value_fn=lambda data: data.active_frequency_hz,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l1_count",
        translation_key="voltage_sag_l1_count",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_sag_l1_count is not None,
        value_fn=lambda data: data.voltage_sag_l1_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l2_count",
        translation_key="voltage_sag_l2_count",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_sag_l2_count is not None,
        value_fn=lambda data: data.voltage_sag_l2_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l3_count",
        translation_key="voltage_sag_l3_count",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_sag_l3_count is not None,
        value_fn=lambda data: data.voltage_sag_l3_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l1_count",
        translation_key="voltage_swell_l1_count",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_swell_l1_count is not None,
        value_fn=lambda data: data.voltage_swell_l1_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l2_count",
        translation_key="voltage_swell_l2_count",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_swell_l2_count is not None,
        value_fn=lambda data: data.voltage_swell_l2_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l3_count",
        translation_key="voltage_swell_l3_count",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.voltage_swell_l3_count is not None,
        value_fn=lambda data: data.voltage_swell_l3_count,
    ),
    HomeWizardSensorEntityDescription(
        key="any_power_fail_count",
        translation_key="any_power_fail_count",
        icon="mdi:transmission-tower-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.any_power_fail_count is not None,
        value_fn=lambda data: data.any_power_fail_count,
    ),
    HomeWizardSensorEntityDescription(
        key="long_power_fail_count",
        translation_key="long_power_fail_count",
        icon="mdi:transmission-tower-off",
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
        key="total_gas_m3",
        translation_key="total_gas_m3",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_gas_m3 is not None,
        value_fn=lambda data: data.total_gas_m3 or None,
    ),
    HomeWizardSensorEntityDescription(
        key="gas_unique_id",
        translation_key="gas_unique_id",
        icon="mdi:alphabetical-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.gas_unique_id is not None,
        value_fn=lambda data: data.gas_unique_id,
    ),
    HomeWizardSensorEntityDescription(
        key="active_liter_lpm",
        translation_key="active_liter_lpm",
        native_unit_of_measurement="l/min",
        icon="mdi:water",
        state_class=SensorStateClass.MEASUREMENT,
        has_fn=lambda data: data.active_liter_lpm is not None,
        value_fn=lambda data: data.active_liter_lpm,
    ),
    HomeWizardSensorEntityDescription(
        key="total_liter_m3",
        translation_key="total_liter_m3",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        icon="mdi:gauge",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_fn=lambda data: data.total_liter_m3 is not None,
        value_fn=lambda data: data.total_liter_m3 or None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize sensors."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        HomeWizardSensorEntity(coordinator, description)
        for description in SENSORS
        if description.has_fn(coordinator.data.data)
    )


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
