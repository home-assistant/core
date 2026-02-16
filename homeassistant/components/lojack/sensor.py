"""Sensor platform for LoJack integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricPotential, UnitOfLength, UnitOfSpeed
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoJackConfigEntry, LoJackCoordinator, LoJackVehicleData
from .const import DOMAIN


def _get_device_name(vehicle: LoJackVehicleData) -> str:
    """Get device name for entity naming."""
    if vehicle.year and vehicle.make and vehicle.model:
        return f"{vehicle.year} {vehicle.make} {vehicle.model}"
    if vehicle.make and vehicle.model:
        return f"{vehicle.make} {vehicle.model}"
    if vehicle.name:
        return vehicle.name
    return "Vehicle"


def _parse_timestamp(timestamp: datetime | str | None) -> datetime | None:
    """Parse timestamp value to datetime."""
    if timestamp is None:
        return None
    if isinstance(timestamp, datetime):
        return timestamp
    try:
        timestamp_str = str(timestamp)
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, AttributeError):
        return None


@dataclass(frozen=True, kw_only=True)
class LoJackSensorEntityDescription(SensorEntityDescription):
    """Describes a LoJack sensor entity."""

    value_fn: Callable[[LoJackVehicleData], float | str | datetime | None]


SENSOR_DESCRIPTIONS: tuple[LoJackSensorEntityDescription, ...] = (
    LoJackSensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.MILES,
        value_fn=lambda v: round(v.odometer, 1) if v.odometer is not None else None,
    ),
    LoJackSensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        value_fn=lambda v: round(v.speed, 1) if v.speed is not None else None,
    ),
    LoJackSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda v: round(v.battery_voltage, 2)
        if v.battery_voltage is not None
        else None,
    ),
    LoJackSensorEntityDescription(
        key="location_last_reported",
        translation_key="location_last_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda v: _parse_timestamp(v.timestamp),
    ),
)

DIAGNOSTIC_SENSOR_DESCRIPTIONS: tuple[LoJackSensorEntityDescription, ...] = (
    LoJackSensorEntityDescription(
        key="make",
        translation_key="make",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda v: v.make,
    ),
    LoJackSensorEntityDescription(
        key="model",
        translation_key="model",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda v: v.model,
    ),
    LoJackSensorEntityDescription(
        key="year",
        translation_key="year",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda v: v.year if v.year else None,
    ),
    LoJackSensorEntityDescription(
        key="vin",
        translation_key="vin",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda v: v.vin,
    ),
    LoJackSensorEntityDescription(
        key="license_plate",
        translation_key="license_plate",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda v: v.license_plate,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[LoJackSensor] = []

    if coordinator.data:
        for vehicle in coordinator.data.values():
            device_name = _get_device_name(vehicle)
            entities.extend(
                LoJackSensor(coordinator, vehicle, device_name, description)
                for description in SENSOR_DESCRIPTIONS
            )
            entities.extend(
                LoJackSensor(coordinator, vehicle, device_name, description)
                for description in DIAGNOSTIC_SENSOR_DESCRIPTIONS
            )

    async_add_entities(entities)


class LoJackSensor(CoordinatorEntity[LoJackCoordinator], SensorEntity):
    """Representation of a LoJack sensor."""

    entity_description: LoJackSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LoJackCoordinator,
        vehicle: LoJackVehicleData,
        device_name: str,
        description: LoJackSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = vehicle.device_id

        self._attr_unique_id = f"{vehicle.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.device_id)},
            name=device_name,
            manufacturer="Spireon LoJack",
            model=f"{vehicle.make} {vehicle.model}"
            if vehicle.make and vehicle.model
            else vehicle.make,
            serial_number=vehicle.vin,
        )

    @property
    def _vehicle(self) -> LoJackVehicleData | None:
        """Get current vehicle data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the sensor value."""
        if vehicle := self._vehicle:
            return self.entity_description.value_fn(vehicle)
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
