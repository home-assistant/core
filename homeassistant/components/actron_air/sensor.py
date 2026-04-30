"""Sensor platform for Actron Air integration."""

from collections.abc import Callable
from dataclasses import dataclass

from actron_neo_api import ActronAirStatus
from actron_neo_api.models.zone import ActronAirPeripheral

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
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator
from .entity import ActronAirAcEntity, ActronAirPeripheralEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ActronAirSensorEntityDescription(SensorEntityDescription):
    """Describes Actron Air sensor entity."""

    value_fn: Callable[[ActronAirStatus], str | float | int | None]


@dataclass(frozen=True, kw_only=True)
class ActronAirPeripheralSensorEntityDescription(SensorEntityDescription):
    """Describes Actron Air peripheral sensor entity."""

    value_fn: Callable[[ActronAirPeripheral], float | None]


SENSORS: tuple[ActronAirSensorEntityDescription, ...] = (
    ActronAirSensorEntityDescription(
        key="compressor_mode",
        translation_key="compressor_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_mode,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_chasing_temperature",
        translation_key="compressor_chasing_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_chasing_temperature,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_live_temperature",
        translation_key="compressor_live_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_live_temperature,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_power",
        translation_key="compressor_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_power,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_speed",
        translation_key="compressor_speed",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_speed,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_capacity",
        translation_key="compressor_capacity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.live_aircon.compressor_capacity,
    ),
    ActronAirSensorEntityDescription(
        key="fan_rpm",
        translation_key="fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.live_aircon.fan_rpm,
    ),
    ActronAirSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda status: status.outdoor_temperature,
    ),
)

PERIPHERAL_SENSORS: tuple[ActronAirPeripheralSensorEntityDescription, ...] = (
    ActronAirPeripheralSensorEntityDescription(
        key="temperature",
        translation_key="peripheral_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda peripheral: peripheral.temperature,
    ),
    ActronAirPeripheralSensorEntityDescription(
        key="humidity",
        translation_key="peripheral_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda peripheral: peripheral.humidity,
    ),
    ActronAirPeripheralSensorEntityDescription(
        key="battery",
        translation_key="peripheral_battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda peripheral: peripheral.battery_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air sensor entities."""
    system_coordinators = entry.runtime_data.system_coordinators
    entities: list[SensorEntity] = []

    for coordinator in system_coordinators.values():
        entities.extend(
            ActronAirSensor(coordinator, description) for description in SENSORS
        )
        entities.extend(
            ActronAirPeripheralSensor(coordinator, peripheral, description)
            for peripheral in coordinator.data.peripherals
            for description in PERIPHERAL_SENSORS
        )

    async_add_entities(entities)


class ActronAirSensor(ActronAirAcEntity, SensorEntity):
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
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def native_value(self) -> str | float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class ActronAirPeripheralSensor(ActronAirPeripheralEntity, SensorEntity):
    """Representation of an Actron Air peripheral sensor."""

    entity_description: ActronAirPeripheralSensorEntityDescription

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        peripheral: ActronAirPeripheral,
        description: ActronAirPeripheralSensorEntityDescription,
    ) -> None:
        """Initialize the peripheral sensor."""
        super().__init__(coordinator, peripheral)
        self.entity_description = description
        self._attr_unique_id = f"{peripheral.serial_number}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if (peripheral := self._peripheral) is None:
            return None
        return self.entity_description.value_fn(peripheral)
