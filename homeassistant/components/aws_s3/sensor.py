"""Support for AWS S3 sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import S3ConfigEntry, SensorData
from .entity import S3Entity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class S3SensorEntityDescription(SensorEntityDescription):
    """Describes an AWS S3 sensor entity."""

    value_fn: Callable[[SensorData], StateType]


SENSORS: tuple[S3SensorEntityDescription, ...] = (
    S3SensorEntityDescription(
        key="backups_size",
        translation_key="backups_size",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.all_backups_size,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AWS S3 sensor based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        S3SensorEntity(coordinator, description) for description in SENSORS
    )


class S3SensorEntity(S3Entity, SensorEntity):
    """Defines an AWS S3 sensor entity."""

    entity_description: S3SensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
