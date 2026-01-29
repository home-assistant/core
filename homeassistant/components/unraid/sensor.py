"""Sensor entities for Unraid integration using entity descriptions."""

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
from homeassistant.const import PERCENTAGE, UnitOfInformation, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import UnraidConfigEntry, UnraidSystemCoordinator, UnraidSystemData
from .entity import UnraidEntityDescription, UnraidSystemEntity

# Coordinator-based, no polling needed
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class UnraidSensorEntityDescription(UnraidEntityDescription, SensorEntityDescription):
    """Describes an Unraid sensor entity."""

    value_fn: Callable[[UnraidSystemData], StateType | datetime]


# System sensor descriptions - limited set for initial PR
SYSTEM_SENSORS: tuple[UnraidSensorEntityDescription, ...] = (
    UnraidSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.metrics.cpu_percent,
    ),
    UnraidSensorEntityDescription(
        key="cpu_temp",
        translation_key="cpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.metrics.cpu_temperature,
    ),
    UnraidSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.metrics.memory_percent,
    ),
    UnraidSensorEntityDescription(
        key="ram_used",
        translation_key="ram_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        value_fn=lambda data: data.metrics.memory_used,
    ),
    UnraidSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.metrics.uptime,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator = entry.runtime_data.system_coordinator

    async_add_entities(
        UnraidSensorEntity(coordinator, description) for description in SYSTEM_SENSORS
    )


class UnraidSensorEntity(UnraidSystemEntity, SensorEntity):
    """Sensor entity for Unraid system metrics."""

    entity_description: UnraidSensorEntityDescription

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        entity_description: UnraidSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
