"""Support for Paperless-ngx sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any

from pypaperless import Paperless
from pypaperless.models.common import StatusType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_SENSOR_DOCUMENT_COUNT,
    ENTITY_SENSOR_INBOX_COUNT,
    ENTITY_SENSOR_STATUS_CELERY,
    ENTITY_SENSOR_STATUS_CLASSIFIER,
    ENTITY_SENSOR_STATUS_DATABASE,
    ENTITY_SENSOR_STATUS_INDEX,
    ENTITY_SENSOR_STATUS_REDIS,
    ENTITY_SENSOR_STORAGE_AVAILABLE,
    ENTITY_SENSOR_STORAGE_TOTAL,
)
from .coordinator import PaperlessConfigEntry, PaperlessCoordinator, PaperlessData
from .entity import PaperlessCoordinatorEntity
from .helpers import build_state_fn, bytes_to_gb_converter

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 2


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: Callable[[PaperlessData], Any] | None = None
    attributes_fn: Callable[[PaperlessData], dict[str, str | None]] | None = None


SENSOR_DESCRIPTIONS: tuple[PaperlessEntityDescription, ...] = (
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_DOCUMENT_COUNT,
        translation_key=ENTITY_SENSOR_DOCUMENT_COUNT,
        icon="mdi:file-document-multiple",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(lambda data: data.document_count),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_INBOX_COUNT,
        translation_key=ENTITY_SENSOR_INBOX_COUNT,
        icon="mdi:tray-full",
        state_class=SensorStateClass.TOTAL,
        value_fn=build_state_fn(lambda data: data.inbox_count),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STORAGE_TOTAL,
        translation_key=ENTITY_SENSOR_STORAGE_TOTAL,
        icon="mdi:harddisk",
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
        icon="mdi:harddisk",
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
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=build_state_fn(
            lambda data: data.status.database.status
            if data.status and data.status.database
            else None,
        ),
        attributes_fn=lambda data: {
            "error": str(data.status.database.error)
            if data.status and data.status.database
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_REDIS,
        translation_key=ENTITY_SENSOR_STATUS_REDIS,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=build_state_fn(
            lambda data: data.status.tasks.redis_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            "error": str(data.status.tasks.redis_error)
            if data.status and data.status.tasks
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_CELERY,
        translation_key=ENTITY_SENSOR_STATUS_CELERY,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=build_state_fn(
            lambda data: data.status.tasks.celery_status
            if data.status and data.status.tasks
            else None,
        ),
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_INDEX,
        translation_key=ENTITY_SENSOR_STATUS_INDEX,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=build_state_fn(
            lambda data: data.status.tasks.index_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            "last_modified": str(data.status.tasks.index_last_modified)
            if data.status and data.status.tasks
            else None,
            "error": str(data.status.tasks.index_error)
            if data.status and data.status.tasks
            else None,
        },
    ),
    PaperlessEntityDescription(
        key=ENTITY_SENSOR_STATUS_CLASSIFIER,
        translation_key=ENTITY_SENSOR_STATUS_CLASSIFIER,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=build_state_fn(
            lambda data: data.status.tasks.classifier_status
            if data.status and data.status.tasks
            else None,
        ),
        attributes_fn=lambda data: {
            "last_trained": str(data.status.tasks.classifier_last_trained)
            if data.status and data.status.tasks
            else None,
            "error": str(data.status.tasks.classifier_error)
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
        data: Paperless,
        entry: PaperlessConfigEntry,
        description: PaperlessEntityDescription,
    ) -> None:
        """Initialize Paperless-ngx coordinator sensor."""
        super().__init__(data, entry, description, coordinator)
        self.paperless_data = data
        self._attr_unique_id = f"{DOMAIN}__{entry.entry_id}_sensor_{description.key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value_fn = self.entity_description.value_fn
        attributes_fn = self.entity_description.attributes_fn

        if value_fn is None:
            raise NotImplementedError

        state = value_fn(self.coordinator.data)

        if state is None:
            self._attr_native_value = None
            self._attr_available = False
        else:
            self._attr_native_value = state.value if isinstance(state, Enum) else state
            self._attr_available = True

        self._attr_extra_state_attributes = {}
        if attributes_fn:
            self._attr_extra_state_attributes.update(
                attributes_fn(self.coordinator.data)
            )

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensors."""
    data = entry.runtime_data
    coordinator = PaperlessCoordinator(hass, entry, data)
    await coordinator.async_request_refresh()

    entities = []

    for description_status in SENSOR_DESCRIPTIONS:
        entity = PaperlessSensor(
            coordinator,
            data,
            entry,
            description_status,
        )
        entities.append(entity)

    async_add_entities(entities)

    await coordinator.async_config_entry_first_refresh()
