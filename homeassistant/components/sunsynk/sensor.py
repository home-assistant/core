"""Sensors for the Sunsynk integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    SunsynkConfigEntry,
    SunsynkDataUpdateCoordinator,
    SunsynkInverterData,
)


@dataclass(frozen=True, kw_only=True)
class SunsynkSensorEntityDescription(SensorEntityDescription):
    """Describes a Sunsynk sensor entity."""

    value_fn: Callable[[SunsynkInverterData], StateType]


SENSORS: tuple[SunsynkSensorEntityDescription, ...] = (
    SunsynkSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.solar.get_power(),
    ),
    SunsynkSensorEntityDescription(
        key="solar_energy_today",
        translation_key="solar_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.solar.generated_today,
    ),
    SunsynkSensorEntityDescription(
        key="solar_energy_total",
        translation_key="solar_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.solar.generated_total,
    ),
    SunsynkSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.grid.get_total_power(),
    ),
    SunsynkSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.grid.fac,
    ),
    SunsynkSensorEntityDescription(
        key="grid_import_today",
        translation_key="grid_import_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.today_import,
    ),
    SunsynkSensorEntityDescription(
        key="grid_import_total",
        translation_key="grid_import_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.total_import,
    ),
    SunsynkSensorEntityDescription(
        key="grid_export_today",
        translation_key="grid_export_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.today_export,
    ),
    SunsynkSensorEntityDescription(
        key="grid_export_total",
        translation_key="grid_export_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.total_export,
    ),
    SunsynkSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery.power,
    ),
    SunsynkSensorEntityDescription(
        key="battery_state_of_charge",
        translation_key="battery_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery.soc,
    ),
    SunsynkSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery.voltage,
    ),
    SunsynkSensorEntityDescription(
        key="battery_current",
        translation_key="battery_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery.current,
    ),
    SunsynkSensorEntityDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery.temp,
    ),
    SunsynkSensorEntityDescription(
        key="battery_charge_today",
        translation_key="battery_charge_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.charge_today,
    ),
    SunsynkSensorEntityDescription(
        key="battery_charge_total",
        translation_key="battery_charge_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.charge_total,
    ),
    SunsynkSensorEntityDescription(
        key="battery_discharge_today",
        translation_key="battery_discharge_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.discharge_today,
    ),
    SunsynkSensorEntityDescription(
        key="battery_discharge_total",
        translation_key="battery_discharge_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.discharge_total,
    ),
    SunsynkSensorEntityDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.load.get_total_power(),
    ),
    SunsynkSensorEntityDescription(
        key="load_energy_today",
        translation_key="load_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.load.daily_used,
    ),
    SunsynkSensorEntityDescription(
        key="load_energy_total",
        translation_key="load_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.load.total_used,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunsynkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sunsynk sensors from a config entry."""
    async_add_entities(
        SunsynkSensorEntity(coordinator, description)
        for coordinator in entry.runtime_data
        for description in SENSORS
    )


class SunsynkSensorEntity(
    CoordinatorEntity[SunsynkDataUpdateCoordinator], SensorEntity
):
    """A sensor of a Sunsynk inverter."""

    _attr_has_entity_name = True
    entity_description: SunsynkSensorEntityDescription

    def __init__(
        self,
        coordinator: SunsynkDataUpdateCoordinator,
        description: SunsynkSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        inverter = coordinator.inverter
        self._attr_unique_id = f"{inverter.sn}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter.sn)},
            name=inverter.alias or inverter.sn,
            manufacturer="Sunsynk",
            model=inverter.model or None,
            serial_number=inverter.sn,
            sw_version=inverter.version.soft_ver if inverter.version else None,
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
