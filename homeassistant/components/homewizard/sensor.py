"""Creates HomeWizard sensor entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final

from homewizard_energy.models import Data, ExternalDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_NAME,
    ATTR_VIA_DEVICE,
    PERCENTAGE,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass
class HomeWizardEntityDescriptionMixin:
    """Mixin values for HomeWizard entities."""

    value_fn: Callable[[Data], float | int | str | None]


@dataclass
class HomeWizardSensorEntityDescription(
    SensorEntityDescription, HomeWizardEntityDescriptionMixin
):
    """Class describing HomeWizard sensor entities."""


SENSORS: Final[tuple[HomeWizardSensorEntityDescription, ...]] = (
    HomeWizardSensorEntityDescription(
        key="smr_version",
        name="DSMR version",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.smr_version,
    ),
    HomeWizardSensorEntityDescription(
        key="meter_model",
        name="Smart meter model",
        icon="mdi:gauge",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.meter_model,
    ),
    HomeWizardSensorEntityDescription(
        key="unique_meter_id",
        name="Smart meter identifier",
        icon="mdi:alphabetical-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.unique_meter_id,
    ),
    HomeWizardSensorEntityDescription(
        key="wifi_ssid",
        name="Wi-Fi SSID",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.wifi_ssid,
    ),
    HomeWizardSensorEntityDescription(
        key="active_tariff",
        name="Active tariff",
        icon="mdi:calendar-clock",
        value_fn=lambda data: (
            None if data.active_tariff is None else str(data.active_tariff)
        ),
        device_class=SensorDeviceClass.ENUM,
        options=["1", "2", "3", "4"],
    ),
    HomeWizardSensorEntityDescription(
        key="wifi_strength",
        name="Wi-Fi strength",
        icon="mdi:wifi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wifi_strength,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_kwh",
        name="Total power import",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_import_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t1_kwh",
        name="Total power import T1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_import_t1_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t2_kwh",
        name="Total power import T2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_import_t2_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t3_kwh",
        name="Total power import T3",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_import_t3_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_import_t4_kwh",
        name="Total power import T4",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_import_t4_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_kwh",
        name="Total power export",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_export_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t1_kwh",
        name="Total power export T1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_export_t1_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t2_kwh",
        name="Total power export T2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_export_t2_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t3_kwh",
        name="Total power export T3",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_export_t3_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="total_power_export_t4_kwh",
        name="Total power export T4",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power_export_t4_kwh,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_w",
        name="Active power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.active_power_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l1_w",
        name="Active power L1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.active_power_l1_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l2_w",
        name="Active power L2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.active_power_l2_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_l3_w",
        name="Active power L3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.active_power_l3_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l1_v",
        name="Active voltage L1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.active_voltage_l1_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l2_v",
        name="Active voltage L2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.active_voltage_l2_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_voltage_l3_v",
        name="Active voltage L3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.active_voltage_l3_v,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l1_a",
        name="Active current L1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.active_current_l1_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l2_a",
        name="Active current L2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.active_current_l2_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_current_l3_a",
        name="Active current L3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.active_current_l3_a,
    ),
    HomeWizardSensorEntityDescription(
        key="active_frequency_hz",
        name="Active frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.active_frequency_hz,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l1_count",
        name="Voltage sags detected L1",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.voltage_sag_l1_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l2_count",
        name="Voltage sags detected L2",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.voltage_sag_l2_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_sag_l3_count",
        name="Voltage sags detected L3",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.voltage_sag_l3_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l1_count",
        name="Voltage swells detected L1",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.voltage_swell_l1_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l2_count",
        name="Voltage swells detected L2",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.voltage_swell_l2_count,
    ),
    HomeWizardSensorEntityDescription(
        key="voltage_swell_l3_count",
        name="Voltage swells detected L3",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.voltage_swell_l3_count,
    ),
    HomeWizardSensorEntityDescription(
        key="any_power_fail_count",
        name="Power failures detected",
        icon="mdi:transmission-tower-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.any_power_fail_count,
    ),
    HomeWizardSensorEntityDescription(
        key="long_power_fail_count",
        name="Long power failures detected",
        icon="mdi:transmission-tower-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.long_power_fail_count,
    ),
    HomeWizardSensorEntityDescription(
        key="active_power_average_w",
        name="Active average demand",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.active_power_average_w,
    ),
    HomeWizardSensorEntityDescription(
        key="monthly_power_peak_w",
        name="Peak demand current month",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.monthly_power_peak_w,
    ),
    HomeWizardSensorEntityDescription(
        key="active_liter_lpm",
        name="Active water usage",
        native_unit_of_measurement="l/min",
        icon="mdi:water",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.active_liter_lpm,
    ),
    HomeWizardSensorEntityDescription(
        key="total_liter_m3",
        name="Total water usage",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        icon="mdi:gauge",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_liter_m3,
    ),
)

EXTERNAL_SENSORS = {
    ExternalDevice.DeviceType.GAS_METER: SensorEntityDescription(
        key="Gas meter",
        name="Total gas",
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ExternalDevice.DeviceType.HEAT_METER: SensorEntityDescription(
        key="Heat meter",
        name="Total energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ExternalDevice.DeviceType.WARM_WATER_METER: SensorEntityDescription(
        key="Warm water meter",
        name="Total water",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ExternalDevice.DeviceType.WATER_METER: SensorEntityDescription(
        key="Water meter",
        name="Total water",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ExternalDevice.DeviceType.INLET_HEAT_METER: SensorEntityDescription(
        key="Inlet heat meter",
        name="Total energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize sensors."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Migrate original gas meter sensor to ExternalDevice
    ent_reg = entity_registry.async_get(hass)

    if (
        entity_id := ent_reg.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{entry.unique_id}_total_gas_m3"
        )
    ) and coordinator.data.data.gas_unique_id is not None:

        ent_reg.async_update_entity(
            entity_id,
            new_unique_id=f"{DOMAIN}_{coordinator.data.data.gas_unique_id}",
        )

    # Initialize default sensors
    entities: list = [
        HomeWizardSensorEntity(coordinator, entry, description)
        for description in SENSORS
        if description.value_fn(coordinator.data.data) is not None
    ]

    # Initialize external devices
    if coordinator.data.data.external_devices is not None:
        for (unique_id, device) in coordinator.data.data.external_devices.items():

            if description := EXTERNAL_SENSORS.get(device.meter_type):
                entities.append(
                    HomeWizardExternalSensorEntity(coordinator, description, unique_id)
                )

    async_add_entities(entities)


class HomeWizardExternalSensorEntity(HomeWizardEntity, SensorEntity):
    """Representation of externally connected HomeWizard Sensor."""

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        description: SensorEntityDescription,
        device_unique_id: str,
    ) -> None:
        """Initialize Externally connected HomeWizard Sensors."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{device_unique_id}"
        self._device_id = device_unique_id
        self.entity_description = description

        if self._attr_device_info is not None:
            self._attr_device_info[ATTR_IDENTIFIERS] = {(DOMAIN, self._attr_unique_id)}
            self._attr_device_info[
                ATTR_NAME
            ] = f"{self.entity_description.key} ({self._device_id})"

            if self.coordinator.data.device.serial is not None:
                self._attr_device_info[ATTR_VIA_DEVICE] = (
                    DOMAIN,
                    self.coordinator.data.device.serial,
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
        return super().available and self.native_value is not None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement based on device unit."""
        if (device := self.device) is None:
            return None

        if device.unit == "m3":
            return UnitOfVolume.CUBIC_METERS

        return device.unit


class HomeWizardSensorEntity(HomeWizardEntity, SensorEntity):
    """Representation of a HomeWizard Sensor."""

    entity_description: HomeWizardSensorEntityDescription

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
        description: HomeWizardSensorEntityDescription,
    ) -> None:
        """Initialize Sensor Domain."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

        # Special case for export, not everyone has solar panels
        # The chance that 'export' is non-zero when you have solar panels is nil
        if (
            description.key
            in [
                "total_power_export_kwh",
                "total_power_export_t1_kwh",
                "total_power_export_t2_kwh",
                "total_power_export_t3_kwh",
                "total_power_export_t4_kwh",
            ]
            and self.native_value == 0
        ):
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float | int | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data.data)

    @property
    def available(self) -> bool:
        """Return availability of meter."""
        return super().available and self.native_value is not None
