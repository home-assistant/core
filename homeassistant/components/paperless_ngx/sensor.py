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

from .const import (
    DOMAIN,
    ENTITY_ATTRIBUTE_ERROR,
    ENTITY_ATTRIBUTE_LAST_MODIFIED,
    ENTITY_ATTRIBUTE_LAST_RUN,
    ENTITY_ATTRIBUTE_LAST_TRAINED,
    ENTITY_SENSOR_CHARACTERS_COUNT,
    ENTITY_SENSOR_CORRESPONDENT_COUNT,
    ENTITY_SENSOR_DOCUMENT_TYPE_COUNT,
    ENTITY_SENSOR_DOCUMENTS_INBOX,
    ENTITY_SENSOR_DOCUMENTS_TOTAL,
    ENTITY_SENSOR_STATUS_CELERY,
    ENTITY_SENSOR_STATUS_CLASSIFIER,
    ENTITY_SENSOR_STATUS_DATABASE,
    ENTITY_SENSOR_STATUS_INDEX,
    ENTITY_SENSOR_STATUS_REDIS,
    ENTITY_SENSOR_STATUS_SANITY,
    ENTITY_SENSOR_STORAGE_AVAILABLE,
    ENTITY_SENSOR_STORAGE_TOTAL,
    ENTITY_SENSOR_TAG_COUNT,
)
from .coordinator import (
    PaperlessConfigEntry,
    PaperlessCoordinator,
    PaperlessData,
    PaperlessRuntimeData,
)
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
        key=ENTITY_SENSOR_DOCUMENTS_TOTAL,
        translation_key=ENTITY_SENSOR_DOCUMENTS_TOTAL,
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.documents_total if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_DOCUMENTS_INBOX,
        translation_key=ENTITY_SENSOR_DOCUMENTS_INBOX,
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.documents_inbox if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_CHARACTERS_COUNT,
        translation_key=ENTITY_SENSOR_CHARACTERS_COUNT,
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.character_count if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_TAG_COUNT,
        translation_key=ENTITY_SENSOR_TAG_COUNT,
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.tag_count if data.statistics else None,
        ),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_CORRESPONDENT_COUNT,
        translation_key=ENTITY_SENSOR_CORRESPONDENT_COUNT,
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.correspondent_count
            if data.statistics
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_DOCUMENT_TYPE_COUNT,
        translation_key=ENTITY_SENSOR_DOCUMENT_TYPE_COUNT,
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(
            lambda data: data.statistics.document_type_count
            if data.statistics
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STORAGE_TOTAL,
        translation_key=ENTITY_SENSOR_STORAGE_TOTAL,
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
        key=ENTITY_SENSOR_STORAGE_AVAILABLE,
        translation_key=ENTITY_SENSOR_STORAGE_AVAILABLE,
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
        key=ENTITY_SENSOR_STATUS_DATABASE,
        translation_key=ENTITY_SENSOR_STATUS_DATABASE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.database.status
            if data.status and data.status.database
            else None,
        ),
        attributes_fn=lambda data: {
            ENTITY_ATTRIBUTE_ERROR: str(data.status.database.error)
            if data.status and data.status.database
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_REDIS,
        translation_key=ENTITY_SENSOR_STATUS_REDIS,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.redis_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            ENTITY_ATTRIBUTE_ERROR: str(data.status.tasks.redis_error)
            if data.status and data.status.tasks
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_CELERY,
        translation_key=ENTITY_SENSOR_STATUS_CELERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.celery_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            ENTITY_ATTRIBUTE_ERROR: str(data.status.tasks.celery_error)
            if data.status and data.status.tasks
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_INDEX,
        translation_key=ENTITY_SENSOR_STATUS_INDEX,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.index_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            ENTITY_ATTRIBUTE_LAST_MODIFIED: str(data.status.tasks.index_last_modified)
            if data.status and data.status.tasks
            else None,
            ENTITY_ATTRIBUTE_ERROR: str(data.status.tasks.index_error)
            if data.status and data.status.tasks
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_CLASSIFIER,
        translation_key=ENTITY_SENSOR_STATUS_CLASSIFIER,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.classifier_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            ENTITY_ATTRIBUTE_LAST_TRAINED: str(
                data.status.tasks.classifier_last_trained
            )
            if data.status and data.status.tasks
            else None,
            ENTITY_ATTRIBUTE_ERROR: str(data.status.tasks.classifier_error)
            if data.status and data.status.tasks
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_SANITY,
        translation_key=ENTITY_SENSOR_STATUS_SANITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=enum_values_to_lower(StatusType),
        value_fn=build_state_fn(
            lambda data: data.status.tasks.sanity_check_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            ENTITY_ATTRIBUTE_LAST_RUN: str(data.status.tasks.sanity_check_last_run)
            if data.status and data.status.tasks
            else None,
            ENTITY_ATTRIBUTE_ERROR: str(data.status.tasks.sanity_check_error)
            if data.status and data.status.tasks
            else None,
        },
    ),
)


class PaperlessSensor(
    PaperlessCoordinatorEntity[PaperlessCoordinator],
    SensorEntity,
):
    """Defines a Paperless-ngx coordinator sensor."""

    entity_description: PaperlessEntityDescription

    def __init__(
        self,
        coordinator: PaperlessCoordinator,
        data: PaperlessRuntimeData,
        entry: PaperlessConfigEntry,
        description: PaperlessEntityDescription,
    ) -> None:
        """Initialize Paperless-ngx sensor."""
        super().__init__(data, entry, description, coordinator)
        self._attr_unique_id = f"{DOMAIN}__{entry.entry_id}_sensor_{description.key}"

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

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return additional state attributes."""
        attributes_fn = self.entity_description.attributes_fn
        return attributes_fn(self.coordinator.data) if attributes_fn else {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensors."""
    data = entry.runtime_data

    async_add_entities(
        [
            PaperlessSensor(data.coordinator, data, entry, description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )
