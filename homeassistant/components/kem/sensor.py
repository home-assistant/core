"""Support for KEM sensors."""

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

from .const import DEVICE_DATA_DEVICES, DEVICE_DATA_ID
from .coordinator import KemConfigEntry
from .entity import KemEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KemSensorEntityDescription(SensorEntityDescription):
    """Class describing Kem sensor entities."""

    use_device_key: bool = False


SENSORS: tuple[KemSensorEntityDescription, ...] = (
    KemSensorEntityDescription(
        key="engineSpeedRpm",
        translation_key="engine_speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    ),
    KemSensorEntityDescription(
        key="engineOilPressurePsi",
        translation_key="engine_oil_pressure",
        native_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="engineCoolantTempF",
        translation_key="engine_coolant_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="batteryVoltageV",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="lubeOilTempF",
        translation_key="lube_oil_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KemSensorEntityDescription(
        key="controllerTempF",
        translation_key="controller_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="engineCompartmentTempF",
        translation_key="engine_compartment_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KemSensorEntityDescription(
        key="engineFrequencyHz",
        translation_key="engine_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="status",
        icon="mdi:home-lightning-bolt",
        translation_key="generator_status",
        use_device_key=True,
    ),
    KemSensorEntityDescription(
        key="engineState",
        icon="mdi:home-lightning-bolt",
        translation_key="engine_state",
    ),
    KemSensorEntityDescription(
        key="powerSource",
        icon="mdi:home-lightning-bolt",
        translation_key="power_source",
    ),
    KemSensorEntityDescription(
        key="totalOperationHours",
        translation_key="total_operation",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    KemSensorEntityDescription(
        key="totalRuntimeHours",
        translation_key="total_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_device_key=True,
    ),
    KemSensorEntityDescription(
        key="runtimeSinceLastMaintenanceHours",
        translation_key="runtime_since_last_maintenance",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    KemSensorEntityDescription(
        key="deviceIpAddress",
        icon="mdi:ip-network",
        translation_key="device_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_device_key=True,
    ),
    KemSensorEntityDescription(
        key="serverIpAddress",
        icon="mdi:server-network",
        translation_key="server_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    KemSensorEntityDescription(
        key="utilityVoltageV",
        translation_key="utility_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="generatorVoltageAvgV",
        translation_key="generator_voltage_avg",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="generatorLoadW",
        translation_key="generator_load",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KemSensorEntityDescription(
        key="generatorLoadPercent",
        translation_key="generator_load_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KemConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""

    homes = config_entry.runtime_data.homes
    coordinators = config_entry.runtime_data.coordinators
    async_add_entities(
        [
            KemSensorEntity(
                coordinators[device_data[DEVICE_DATA_ID]],
                device_data[DEVICE_DATA_ID],
                device_data,
                sensor_description,
                sensor_description.use_device_key,
            )
            for home_data in homes
            for device_data in home_data[DEVICE_DATA_DEVICES]
            for sensor_description in SENSORS
        ]
    )


class KemSensorEntity(KemEntity, SensorEntity):
    """Representation of an KEM sensor."""

    @property
    def native_value(self) -> str:
        """Return the sensors state."""
        return self._kem_value
