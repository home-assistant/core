"""Sensors for the Sunsynk integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from sunsynk_modbus import SunsynkInverter

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    SunsynkConfigEntry,
    SunsynkInverterData,
    SunsynkModbusCoordinator,
)
from .entity import (
    SunsynkBatteryEntity,
    SunsynkInverterEntity,
    SunsynkModbusBatteryEntity,
    SunsynkModbusInverterEntity,
)


@dataclass(frozen=True, kw_only=True)
class SunsynkSensorEntityDescription(SensorEntityDescription):
    """Describes a Sunsynk sensor entity."""

    value_fn: Callable[[SunsynkInverterData], StateType]
    modbus_value_fn: Callable[[SunsynkInverter], StateType]


SENSORS_INVERTER: tuple[SunsynkSensorEntityDescription, ...] = (
    SunsynkSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.solar.get_power(),
        modbus_value_fn=lambda inverter: inverter.readings.pv_power,
    ),
    SunsynkSensorEntityDescription(
        key="solar_energy_today",
        translation_key="solar_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.solar.generated_today,
        modbus_value_fn=lambda inverter: inverter.energy.day_pv_energy,
    ),
    SunsynkSensorEntityDescription(
        key="solar_energy_total",
        translation_key="solar_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.solar.generated_total,
        modbus_value_fn=lambda inverter: inverter.energy.total_pv_energy,
    ),
    SunsynkSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.grid.get_total_power(),
        modbus_value_fn=lambda inverter: inverter.readings.grid_power,
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
        modbus_value_fn=lambda inverter: inverter.readings.grid_frequency,
    ),
    SunsynkSensorEntityDescription(
        key="grid_import_today",
        translation_key="grid_import_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.today_import,
        modbus_value_fn=lambda inverter: inverter.energy.day_grid_import,
    ),
    SunsynkSensorEntityDescription(
        key="grid_import_total",
        translation_key="grid_import_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.total_import,
        modbus_value_fn=lambda inverter: inverter.energy.total_grid_import,
    ),
    SunsynkSensorEntityDescription(
        key="grid_export_today",
        translation_key="grid_export_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.today_export,
        modbus_value_fn=lambda inverter: inverter.energy.day_grid_export,
    ),
    SunsynkSensorEntityDescription(
        key="grid_export_total",
        translation_key="grid_export_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.grid.total_export,
        modbus_value_fn=lambda inverter: inverter.energy.total_grid_export,
    ),
    SunsynkSensorEntityDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.load.get_total_power(),
        modbus_value_fn=lambda inverter: inverter.readings.load_power,
    ),
    SunsynkSensorEntityDescription(
        key="load_energy_today",
        translation_key="load_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.load.daily_used,
        modbus_value_fn=lambda inverter: inverter.energy.day_load_energy,
    ),
    SunsynkSensorEntityDescription(
        key="load_energy_total",
        translation_key="load_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.load.total_used,
        modbus_value_fn=lambda inverter: inverter.energy.total_load_energy,
    ),
)

SENSORS_BATTERY: tuple[SunsynkSensorEntityDescription, ...] = (
    SunsynkSensorEntityDescription(
        key="battery_power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery.power,
        modbus_value_fn=lambda inverter: inverter.readings.battery_power,
    ),
    SunsynkSensorEntityDescription(
        key="battery_state_of_charge",
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery.soc,
        modbus_value_fn=lambda inverter: inverter.readings.battery_soc,
    ),
    SunsynkSensorEntityDescription(
        key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery.voltage,
        modbus_value_fn=lambda inverter: inverter.readings.battery_voltage,
    ),
    SunsynkSensorEntityDescription(
        key="battery_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery.current,
        modbus_value_fn=lambda inverter: inverter.readings.battery_current,
    ),
    SunsynkSensorEntityDescription(
        key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery.temp,
        modbus_value_fn=lambda inverter: inverter.readings.battery_temperature,
    ),
    SunsynkSensorEntityDescription(
        key="battery_charge_today",
        translation_key="charge_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.charge_today,
        modbus_value_fn=lambda inverter: inverter.energy.day_battery_charge,
    ),
    SunsynkSensorEntityDescription(
        key="battery_charge_total",
        translation_key="charge_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.charge_total,
        modbus_value_fn=lambda inverter: inverter.energy.total_battery_charge,
    ),
    SunsynkSensorEntityDescription(
        key="battery_discharge_today",
        translation_key="discharge_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.discharge_today,
        modbus_value_fn=lambda inverter: inverter.energy.day_battery_discharge,
    ),
    SunsynkSensorEntityDescription(
        key="battery_discharge_total",
        translation_key="discharge_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery.discharge_total,
        modbus_value_fn=lambda inverter: inverter.energy.total_battery_discharge,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunsynkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sunsynk sensors from a config entry."""
    entities: list[SensorEntity] = []
    runtime_data = entry.runtime_data
    if isinstance(runtime_data, SunsynkModbusCoordinator):
        entities.extend(
            SunsynkModbusInverterSensorEntity(runtime_data, description)
            for description in SENSORS_INVERTER
        )
        if runtime_data.inverter.has_battery:
            entities.extend(
                SunsynkModbusBatterySensorEntity(runtime_data, description)
                for description in SENSORS_BATTERY
            )
        async_add_entities(entities)
        return

    for coordinator in runtime_data:
        entities.extend(
            SunsynkInverterSensorEntity(coordinator, description)
            for description in SENSORS_INVERTER
        )
        if coordinator.data.battery.is_present:
            entities.extend(
                SunsynkBatterySensorEntity(coordinator, description)
                for description in SENSORS_BATTERY
            )
    async_add_entities(entities)


class SunsynkInverterSensorEntity(SunsynkInverterEntity, SensorEntity):
    """A sensor of a Sunsynk inverter."""

    entity_description: SunsynkSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class SunsynkBatterySensorEntity(SunsynkBatteryEntity, SensorEntity):
    """A sensor of the battery of a Sunsynk inverter."""

    entity_description: SunsynkSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class SunsynkModbusInverterSensorEntity(SunsynkModbusInverterEntity, SensorEntity):
    """A sensor of a Sunsynk inverter that uses Modbus."""

    entity_description: SunsynkSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.modbus_value_fn(self.coordinator.data)


class SunsynkModbusBatterySensorEntity(SunsynkModbusBatteryEntity, SensorEntity):
    """A sensor of the battery of a Sunsynk inverter that uses Modbus."""

    entity_description: SunsynkSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.modbus_value_fn(self.coordinator.data)
