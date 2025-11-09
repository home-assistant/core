"""Support for GoogleDrive sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .coordinator import (
    GoogleDriveConfigEntry,
    GoogleDriveCoordinatorData,
    GoogleDriveDataUpdateCoordinator,
)
from .entity import GoogleDriveEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GoogleDriveSensorEntityDescription(SensorEntityDescription):
    """Describes GoogleDrive sensor entity."""

    value_fn: Callable[[GoogleDriveCoordinatorData], datetime | StateType]


SENSORS: tuple[GoogleDriveSensorEntityDescription, ...] = (
    GoogleDriveSensorEntityDescription(
        key="storage_total",
        translation_key="storage_total",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.storage_quota.limit,
    ),
    GoogleDriveSensorEntityDescription(
        key="storage_used",
        translation_key="storage_used",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.storage_quota.usage,
    ),
    GoogleDriveSensorEntityDescription(
        key="storage_used_in_drive",
        translation_key="storage_used_in_drive",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.storage_quota.usage_in_drive,
        entity_registry_enabled_default=False,
    ),
    GoogleDriveSensorEntityDescription(
        key="storage_used_in_drive_trash",
        translation_key="storage_used_in_drive_trash",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.storage_quota.usage_in_trash,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleDriveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GoogleDrive sensor based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        GoogleDriveSensorEntity(coordinator, description) for description in SENSORS
    )


class GoogleDriveSensorEntity(GoogleDriveEntity, SensorEntity):
    """Defines a Google Drive sensor entity."""

    entity_description: GoogleDriveSensorEntityDescription

    def __init__(
        self,
        coordinator: GoogleDriveDataUpdateCoordinator,
        description: GoogleDriveSensorEntityDescription,
    ) -> None:
        """Initialize a Google Drive sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{slugify(coordinator.config_entry.unique_id)}_{description.key}"
        )

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
