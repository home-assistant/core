"""Sensor platform for Actron Air integration."""

from collections.abc import Callable
from dataclasses import dataclass

from actron_neo_api import ActronAirPeripheral, ActronAirStatus

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator
from .entity import ActronAirEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ActronAirSensorEntityDescription(SensorEntityDescription):
    """Describes Actron Air sensor entity."""

    value_fn: Callable[[ActronAirStatus], str | int | float | bool | None] | None = None


@dataclass(frozen=True, kw_only=True)
class ActronAirPeripheralSensorEntityDescription(SensorEntityDescription):
    """Describes Actron Air peripheral sensor entity."""

    value_fn: Callable[[ActronAirPeripheral], str | int | float | None] | None = None


AC_SENSORS: tuple[ActronAirSensorEntityDescription, ...] = (
    ActronAirSensorEntityDescription(
        key="compressor_chasing_temperature",
        translation_key="compressor_chasing_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_chasing_temperature,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_live_temperature",
        translation_key="compressor_live_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_live_temperature,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_speed",
        translation_key="compressor_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_speed,
    ),
    ActronAirSensorEntityDescription(
        key="compressor_power",
        translation_key="compressor_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.compressor_power,
    ),
    ActronAirSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.outdoor_temperature,
    ),
)

PERIPHERAL_SENSORS: tuple[ActronAirPeripheralSensorEntityDescription, ...] = (
    ActronAirPeripheralSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda peripheral: peripheral.battery_level,
    ),
    ActronAirPeripheralSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda peripheral: peripheral.humidity,
    ),
    ActronAirPeripheralSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda peripheral: peripheral.temperature,
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


class ActronAirSensor(ActronAirEntity, SensorEntity):
    """Representation of an Actron Air sensor."""

    entity_description: ActronAirSensorEntityDescription
    _attr_entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        description: ActronAirSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._serial_number}_{description.key}"

    @property
    def native_value(self) -> str | int | float | bool | None:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class ActronAirPeripheralSensorEntity(ActronAirEntity, SensorEntity):
    """Representation of an Actron Air peripheral sensor."""

    entity_description: ActronAirPeripheralSensorEntityDescription
    _attr_entity_category = None

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        peripheral: ActronAirPeripheral,
        description: ActronAirPeripheralSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._peripheral = peripheral
        zone = peripheral.zones[0]
        suggested_area = zone.title
        zone_entity_id = f"{self._serial_number}_zone_{zone.zone_id}"

        self.entity_description = description
        self._attr_unique_id = f"{peripheral.serial_number}_{description.key}"
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, peripheral.serial_number)},
            name=f"{peripheral.device_type} {peripheral.logical_address}",
            model=peripheral.device_type,
            suggested_area=suggested_area,
            via_device=(DOMAIN, zone_entity_id),
            serial_number=peripheral.serial_number,
        )

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self._peripheral)
