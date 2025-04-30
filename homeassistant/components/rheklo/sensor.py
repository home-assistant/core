"""Support for Rheklo sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DEVICE_DATA_DEVICES, DEVICE_DATA_ID
from .coordinator import RhekloConfigEntry
from .entity import RhekloEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RhekloSensorEntityDescription(SensorEntityDescription):
    """Class describing Rheklo sensor entities."""

    use_device_key: bool = False


SENSORS: tuple[RhekloSensorEntityDescription, ...] = (
    RhekloSensorEntityDescription(
        key="engineSpeedRpm",
        translation_key="engine_speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    ),
    RhekloSensorEntityDescription(
        key="engineOilPressurePsi",
        translation_key="engine_oil_pressure",
        native_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="engineCoolantTempF",
        translation_key="engine_coolant_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="batteryVoltageV",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="lubeOilTempF",
        translation_key="lube_oil_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RhekloSensorEntityDescription(
        key="controllerTempF",
        translation_key="controller_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="engineCompartmentTempF",
        translation_key="engine_compartment_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RhekloSensorEntityDescription(
        key="engineFrequencyHz",
        translation_key="engine_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="totalOperationHours",
        translation_key="total_operation",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    RhekloSensorEntityDescription(
        key="totalRuntimeHours",
        translation_key="total_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_device_key=True,
    ),
    RhekloSensorEntityDescription(
        key="runtimeSinceLastMaintenanceHours",
        translation_key="runtime_since_last_maintenance",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    RhekloSensorEntityDescription(
        key="deviceIpAddress",
        translation_key="device_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_device_key=True,
    ),
    RhekloSensorEntityDescription(
        key="serverIpAddress",
        translation_key="server_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    RhekloSensorEntityDescription(
        key="utilityVoltageV",
        translation_key="utility_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="generatorVoltageAvgV",
        translation_key="generator_voltage_avg",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="generatorLoadW",
        translation_key="generator_load",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RhekloSensorEntityDescription(
        key="generatorLoadPercent",
        translation_key="generator_load_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RhekloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""

    homes = config_entry.runtime_data.homes
    coordinators = config_entry.runtime_data.coordinators
    async_add_entities(
        RhekloSensorEntity(
            coordinators[device_data[DEVICE_DATA_ID]],
            device_data[DEVICE_DATA_ID],
            device_data,
            sensor_description,
            sensor_description.use_device_key,
        )
        for home_data in homes
        for device_data in home_data[DEVICE_DATA_DEVICES]
        for sensor_description in SENSORS
    )


class RhekloSensorEntity(RhekloEntity, SensorEntity):
    """Representation of a Rheklo sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the sensor state."""
        return self._rheklo_value
