"""Support for Paperless-ngx sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from pypaperless.models.common import StatusType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_flow import PaperlessConfigEntry
from .coordinator import PaperlessCoordinator, PaperlessData
from .entity import PaperlessCoordinatorEntity
from .helpers import build_state_fn, bytes_to_gb_converter, enum_values_to_lower

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 2


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: Callable[[PaperlessData], Any] | None = None
    attributes_fn: Callable[[PaperlessData], dict[str, str | None]] | None = None


SENSOR_DESCRIPTIONS: tuple[PaperlessEntityDescription, ...] = (
    PaperlessEntityDescription(
        key="documents_total",
        translation_key="documents_total",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.documents_total if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key="documents_inbox",
        translation_key="documents_inbox",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.documents_inbox if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key="characters_count",
        translation_key="characters_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.character_count if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key="tag_count",
        translation_key="tag_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.tag_count if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key="correspondent_count",
        translation_key="correspondent_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.correspondent_count
            if data.statistics
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="document_type_count",
        translation_key="document_type_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.document_type_count
            if data.statistics
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="storage_total",
        translation_key="storage_total",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=build_state_fn(
            lambda data: data.status.storage.total
            if data.status and data.status.storage
            else None,
            transform=bytes_to_gb_converter,
        ),
    ),
    PaperlessEntityDescription(
        key="storage_available",
        translation_key="storage_available",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=build_state_fn(
            lambda data: data.status.storage.available
            if data.status and data.status.storage
            else None,
            transform=bytes_to_gb_converter,
        ),
    ),
    PaperlessEntityDescription(
        key="status_database",
        translation_key="status_database",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.database.status
            if data.status and data.status.database
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_database_error",
        translation_key="status_database_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.database.error
            if data.status and data.status.database
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_redis",
        translation_key="status_redis",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.redis_status
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_redis_error",
        translation_key="status_redis_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.redis_error
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_celery",
        translation_key="status_celery",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.celery_status
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_celery_error",
        translation_key="status_celery_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.celery_error
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_index",
        translation_key="status_index",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.index_status
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_index_last_modified",
        translation_key="status_index_last_modified",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATE,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.index_last_modified
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_index_error",
        translation_key="status_index_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.index_error
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_classifier",
        translation_key="status_classifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.classifier_status
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_classifier_last_trained",
        translation_key="status_classifier_last_trained",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATE,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.classifier_last_trained
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_classifier_error",
        translation_key="status_classifier_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.classifier_error
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_sanity",
        translation_key="status_sanity",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.sanity_check_status
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_sanity_last_run",
        translation_key="status_sanity_last_run",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATE,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.sanity_check_last_run
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="status_sanity_error",
        translation_key="status_sanity_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.sanity_check_error
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="latest_version",
        translation_key="latest_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=build_state_fn(
            lambda data: data.remote_version.version
            if data.remote_version is not None
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key="latest_version_last_checked",
        translation_key="latest_version_last_checked",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=build_state_fn(
            lambda data: data.remote_version_last_checked if data is not None else None,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensors."""
    async_add_entities(
        [
            PaperlessSensor(
                entry=entry,
                coordinator=entry.runtime_data,
                description=description,
            )
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class PaperlessSensor(
    PaperlessCoordinatorEntity[PaperlessCoordinator],
    SensorEntity,
):
    """Defines a Paperless-ngx coordinator sensor."""

    entity_description: PaperlessEntityDescription

    def __init__(
        self,
        entry: PaperlessConfigEntry,
        coordinator: PaperlessCoordinator,
        description: PaperlessEntityDescription,
    ) -> None:
        """Initialize Paperless-ngx sensor."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            description=description,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.native_value is not None

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the current value of the sensor."""
        value_fn = self.entity_description.value_fn
        if not value_fn:
            return None
        state = value_fn(self.coordinator.data)
        return state.value.lower() if isinstance(state, Enum) else state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()
