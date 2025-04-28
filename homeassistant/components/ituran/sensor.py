"""Sensors for Ituran vehicles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pyituran import Vehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEGREE,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import IturanConfigEntry
from .coordinator import IturanDataUpdateCoordinator
from .entity import IturanBaseEntity


@dataclass(frozen=True, kw_only=True)
class IturanSensorEntityDescription(SensorEntityDescription):
    """Describes Ituran sensor entity."""

    value_fn: Callable[[Vehicle], StateType | datetime]


SENSOR_TYPES: list[IturanSensorEntityDescription] = [
    IturanSensorEntityDescription(
        key="address",
        translation_key="address",
        entity_registry_enabled_default=False,
        value_fn=lambda vehicle: vehicle.address,
    ),
    IturanSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda vehicle: vehicle.battery_voltage,
    ),
    IturanSensorEntityDescription(
        key="heading",
        translation_key="heading",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda vehicle: vehicle.heading,
    ),
    IturanSensorEntityDescription(
        key="last_update_from_vehicle",
        translation_key="last_update_from_vehicle",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda vehicle: vehicle.last_update,
    ),
    IturanSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=2,
        value_fn=lambda vehicle: vehicle.mileage,
    ),
    IturanSensorEntityDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=0,
        value_fn=lambda vehicle: vehicle.speed,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IturanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ituran sensors from config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        IturanSensor(coordinator, license_plate, description)
        for description in SENSOR_TYPES
        for license_plate in coordinator.data
    )


class IturanSensor(IturanBaseEntity, SensorEntity):
    """Ituran device tracker."""

    entity_description: IturanSensorEntityDescription

    def __init__(
        self,
        coordinator: IturanDataUpdateCoordinator,
        license_plate: str,
        description: IturanSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, license_plate, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.vehicle)
