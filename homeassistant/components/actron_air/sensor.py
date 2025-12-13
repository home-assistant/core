"""Sensor platform for Actron Air integration."""

from dataclasses import dataclass

from actron_neo_api import ActronAirPeripheral

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator
from .entity import ActronAirAcSensor, ActronAirPeripheralSensor

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ActronAirSensorEntityDescription(SensorEntityDescription):
    """Describes Actron Air sensor entity."""

    attribute_name: str | None = None


AC_SENSORS: tuple[ActronAirSensorEntityDescription, ...] = (
    ActronAirSensorEntityDescription(
        key="clean_filter",
        translation_key="clean_filter",
    ),
    ActronAirSensorEntityDescription(
        key="defrost_mode",
        translation_key="defrost_mode",
        entity_registry_enabled_default=False,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_chasing_temperature",
        translation_key="compressor_chasing_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_live_temperature",
        translation_key="compressor_live_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_mode",
        translation_key="compressor_mode",
        entity_registry_enabled_default=False,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_speed",
        translation_key="compressor_speed",
        native_unit_of_measurement="RPM",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_power",
        translation_key="compressor_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ActronAirSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)

PERIPHERAL_SENSORS: tuple[ActronAirSensorEntityDescription, ...] = (
    ActronAirSensorEntityDescription(
        key="battery",
        attribute_name="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ActronAirSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ActronAirSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air sensor platform entities."""
    system_coordinators = entry.runtime_data.system_coordinators
    entities: list[SensorEntity] = []

    for coordinator in system_coordinators.values():
        status = coordinator.data

        # Add AC system sensors
        entities.extend(
            ActronAirSensor(coordinator, description) for description in AC_SENSORS
        )

        # Add peripheral sensors
        for peripheral in status.peripherals:
            entities.extend(
                ActronAirPeripheralSensorEntity(coordinator, peripheral, description)
                for description in PERIPHERAL_SENSORS
            )

    # Register all sensors
    async_add_entities(entities)


class ActronAirSensor(ActronAirAcSensor, SensorEntity):
    """Representation of an Actron Air sensor."""

    entity_description: ActronAirSensorEntityDescription

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        description: ActronAirSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._serial_number}-{description.key}"

    @property
    def native_value(self) -> str | int | float | bool | None:
        """Return the state of the sensor."""
        return getattr(
            self.coordinator.data,
            self.entity_description.attribute_name or self.entity_description.key,
            None,
        )


class ActronAirPeripheralSensorEntity(ActronAirPeripheralSensor, SensorEntity):
    """Representation of an Actron Air peripheral sensor."""

    entity_description: ActronAirSensorEntityDescription

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        peripheral: ActronAirPeripheral,
        description: ActronAirSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, peripheral)
        self.entity_description = description
        self._attr_unique_id = f"{peripheral.serial_number}_{description.key}"

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return getattr(
            self._peripheral,
            self.entity_description.attribute_name or self.entity_description.key,
            None,
        )
