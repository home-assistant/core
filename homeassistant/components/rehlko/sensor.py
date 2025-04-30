"""Support for Rehlko sensors."""

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
from .coordinator import RehlkoConfigEntry
from .entity import RehlkoEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RehlkoSensorEntityDescription(SensorEntityDescription):
    """Class describing Rehlko sensor entities."""

    use_device_key: bool = False


SENSORS: tuple[RehlkoSensorEntityDescription, ...] = (
    RehlkoSensorEntityDescription(
        key="engineSpeedRpm",
        translation_key="engine_speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    ),
    RehlkoSensorEntityDescription(
        key="engineOilPressurePsi",
        translation_key="engine_oil_pressure",
        native_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="engineCoolantTempF",
        translation_key="engine_coolant_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="batteryVoltageV",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="lubeOilTempF",
        translation_key="lube_oil_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RehlkoSensorEntityDescription(
        key="controllerTempF",
        translation_key="controller_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="engineCompartmentTempF",
        translation_key="engine_compartment_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RehlkoSensorEntityDescription(
        key="engineFrequencyHz",
        translation_key="engine_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="totalOperationHours",
        translation_key="total_operation",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    RehlkoSensorEntityDescription(
        key="totalRuntimeHours",
        translation_key="total_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_device_key=True,
    ),
    RehlkoSensorEntityDescription(
        key="runtimeSinceLastMaintenanceHours",
        translation_key="runtime_since_last_maintenance",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    RehlkoSensorEntityDescription(
        key="deviceIpAddress",
        translation_key="device_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_device_key=True,
    ),
    RehlkoSensorEntityDescription(
        key="serverIpAddress",
        translation_key="server_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    RehlkoSensorEntityDescription(
        key="utilityVoltageV",
        translation_key="utility_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="generatorVoltageAvgV",
        translation_key="generator_voltage_avg",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="generatorLoadW",
        translation_key="generator_load",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RehlkoSensorEntityDescription(
        key="generatorLoadPercent",
        translation_key="generator_load_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RehlkoSensorEntityDescription(
        key="status",
        translation_key="generator_status",
        use_device_key=True,
    ),
    RehlkoSensorEntityDescription(
        key="engineState",
        translation_key="engine_state",
    ),
    RehlkoSensorEntityDescription(
        key="powerSource",
        icon="mdi:home-lightning-bolt",
        translation_key="power_source",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RehlkoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""

    homes = config_entry.runtime_data.homes
    coordinators = config_entry.runtime_data.coordinators
    async_add_entities(
        RehlkoSensorEntity(
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


class RehlkoSensorEntity(RehlkoEntity, SensorEntity):
    """Representation of a Rehlko sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the sensor state."""
        return self._rehlko_value
