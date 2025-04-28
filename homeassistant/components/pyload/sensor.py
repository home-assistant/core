"""Support for monitoring pyLoad."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import UNIT_DOWNLOADS
from .coordinator import PyLoadConfigEntry, PyLoadData
from .entity import BasePyLoadEntity

PARALLEL_UPDATES = 0


class PyLoadSensorEntity(StrEnum):
    """pyLoad Sensor Entities."""

    ACTIVE = "active"
    FREE_SPACE = "free_space"
    QUEUE = "queue"
    SPEED = "speed"
    TOTAL = "total"


@dataclass(kw_only=True, frozen=True)
class PyLoadSensorEntityDescription(SensorEntityDescription):
    """Describes pyLoad switch entity."""

    value_fn: Callable[[PyLoadData], StateType]


SENSOR_DESCRIPTIONS: tuple[PyLoadSensorEntityDescription, ...] = (
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.SPEED,
        translation_key=PyLoadSensorEntity.SPEED,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        value_fn=lambda data: data.speed,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.ACTIVE,
        translation_key=PyLoadSensorEntity.ACTIVE,
        native_unit_of_measurement=UNIT_DOWNLOADS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.active,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.QUEUE,
        translation_key=PyLoadSensorEntity.QUEUE,
        native_unit_of_measurement=UNIT_DOWNLOADS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.queue,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.TOTAL,
        translation_key=PyLoadSensorEntity.TOTAL,
        native_unit_of_measurement=UNIT_DOWNLOADS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.total,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.FREE_SPACE,
        translation_key=PyLoadSensorEntity.FREE_SPACE,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        value_fn=lambda data: data.free_space,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PyLoadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the pyLoad sensors."""

    coordinator = entry.runtime_data

    async_add_entities(
        (
            PyLoadSensor(
                coordinator=coordinator,
                entity_description=description,
            )
            for description in SENSOR_DESCRIPTIONS
        ),
    )


class PyLoadSensor(BasePyLoadEntity, SensorEntity):
    """Representation of a pyLoad sensor."""

    entity_description: PyLoadSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
