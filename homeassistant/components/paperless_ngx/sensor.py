"""Support for Paperless-ngx sensors."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pypaperless.models import Status
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

from . import PaperlessConfigEntry, PaperlessData
from .const import (
    DIAGNOSIS_NAME_STATUS_CELERY,
    DIAGNOSIS_NAME_STATUS_CLASSIFIER,
    DIAGNOSIS_NAME_STATUS_DATABASE,
    DIAGNOSIS_NAME_STATUS_INDEX,
    DIAGNOSIS_NAME_STATUS_REDIS,
    DIAGNOSIS_NAME_STORAGE_AVAILABLE,
    DIAGNOSIS_NAME_STORAGE_TOTAL,
    DOMAIN,
    SENSOR_NAME_DOCUMENT_COUNT,
    SENSOR_NAME_INBOX_COUNT,
)
from .coordinator import PaperlessStatusCoordinator
from .entity import PaperlessCoordinatorEntity, PaperlessEntity
from .helpers import (
    PaperlessStatusEntry,
    bytes_to_gb_converter,
    get_paperless_status_entry,
)

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 2


async def get_document_count(data: PaperlessData) -> int | None:
    """Get the number of documents in the system."""
    documents = await data.client.documents.all()
    return len(documents)


async def get_inbox_count(data: PaperlessData) -> int | None:
    """Get the number of documents in the inbox."""
    if not data.inbox_tags:
        return 0

    tag_ids = ",".join([str(tag.id) for tag in data.inbox_tags if tag.id is not None])
    async with data.client.documents.reduce(tags__id__in=tag_ids) as docs:
        inbox_docs = await docs.all()

    return len(inbox_docs)


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: Callable[[PaperlessData], Coroutine[Any, Any, int | None]] | None = None


SENSOR_DESCRIPTIONS: tuple[PaperlessEntityDescription, ...] = (
    PaperlessEntityDescription(
        key=SENSOR_NAME_DOCUMENT_COUNT,
        translation_key=SENSOR_NAME_DOCUMENT_COUNT,
        icon="mdi:file-document-multiple",
        state_class=SensorStateClass.TOTAL,
        value_fn=get_document_count,
    ),
    PaperlessEntityDescription(
        key=SENSOR_NAME_INBOX_COUNT,
        translation_key=SENSOR_NAME_INBOX_COUNT,
        icon="mdi:file-document-alert",
        state_class=SensorStateClass.TOTAL,
        value_fn=get_inbox_count,
    ),
)


@dataclass(frozen=True, kw_only=True)
class PaperlessStatusEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: Callable[[Status], PaperlessStatusEntry] | None = None


STATUS_SENSOR_DESCRIPTION: tuple[PaperlessStatusEntityDescription, ...] = (
    PaperlessStatusEntityDescription(
        key=DIAGNOSIS_NAME_STORAGE_TOTAL,
        translation_key=DIAGNOSIS_NAME_STORAGE_TOTAL,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_paperless_status_entry(
            lambda s: s.storage.total if s and s.storage else None,
            transform=bytes_to_gb_converter,
        ),
    ),
    PaperlessStatusEntityDescription(
        key=DIAGNOSIS_NAME_STORAGE_AVAILABLE,
        translation_key=DIAGNOSIS_NAME_STORAGE_AVAILABLE,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_paperless_status_entry(
            lambda s: s.storage.available if s and s.storage else None,
            transform=bytes_to_gb_converter,
        ),
    ),
    PaperlessStatusEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_DATABASE,
        translation_key=DIAGNOSIS_NAME_STATUS_DATABASE,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_paperless_status_entry(
            lambda s: s.database.status if s and s.database else None,
            lambda s: s.database.error if s and s.database else None,
        ),
    ),
    PaperlessStatusEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_REDIS,
        translation_key=DIAGNOSIS_NAME_STATUS_REDIS,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_paperless_status_entry(
            lambda s: s.tasks.redis_status if s and s.tasks else None,
            lambda s: s.tasks.redis_error if s and s.tasks else None,
        ),
    ),
    PaperlessStatusEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_CELERY,
        translation_key=DIAGNOSIS_NAME_STATUS_CELERY,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_paperless_status_entry(
            lambda s: s.tasks.celery_status if s and s.tasks else None,
        ),
    ),
    PaperlessStatusEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_INDEX,
        translation_key=DIAGNOSIS_NAME_STATUS_INDEX,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_paperless_status_entry(
            lambda s: s.tasks.index_status if s and s.tasks else None,
            lambda s: s.tasks.index_error if s and s.tasks else None,
            lambda s: s.tasks.index_last_modified if s and s.tasks else None,
        ),
    ),
    PaperlessStatusEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_CLASSIFIER,
        translation_key=DIAGNOSIS_NAME_STATUS_CLASSIFIER,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_paperless_status_entry(
            lambda s: s.tasks.classifier_status if s and s.tasks else None,
            lambda s: s.tasks.classifier_error if s and s.tasks else None,
            lambda s: s.tasks.classifier_last_trained if s and s.tasks else None,
        ),
    ),
)


class PaperlessSensor(PaperlessEntity, SensorEntity):
    """Defines a Paperless-ngx sensor."""

    entity_description: PaperlessEntityDescription

    def __init__(
        self,
        data: PaperlessData,
        entry: PaperlessConfigEntry,
        description: PaperlessEntityDescription,
    ) -> None:
        """Initialize Paperless-ngx sensor."""
        super().__init__(data, entry, description)
        self.data = data

    async def _paperless_update(self) -> None:
        value_fn = self.entity_description.value_fn
        if value_fn is None:
            raise NotImplementedError

        self._attr_native_value = await value_fn(self.data)


class PaperlessStatusSensor(
    PaperlessCoordinatorEntity[PaperlessStatusCoordinator],
    SensorEntity,
):
    """Defines a Paperless-ngx coordinator sensor."""

    entity_description: PaperlessStatusEntityDescription

    def __init__(
        self,
        coordinator: PaperlessStatusCoordinator,
        data: PaperlessData,
        entry: PaperlessConfigEntry,
        description: PaperlessStatusEntityDescription,
    ) -> None:
        """Initialize Paperless-ngx coordinator sensor."""
        super().__init__(data, entry, description, coordinator)
        self.paperless_data = data
        self._attr_unique_id = f"{DOMAIN}_{self}_{data.client.base_url}_sensor_{description.key}_{entry.entry_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value_fn = self.entity_description.value_fn
        if value_fn is None:
            raise NotImplementedError

        status_entry = value_fn(self.coordinator.data)

        if status_entry.state is None:
            self._attr_native_value = None
            self._attr_available = False
        else:
            self._attr_native_value = (
                status_entry.state.value
                if isinstance(status_entry.state, StatusType)
                else status_entry.state
            )
            self._attr_available = True

        self._attr_extra_state_attributes = {}

        if status_entry.error:
            self._attr_extra_state_attributes["error_message"] = status_entry.error

        if status_entry.last_run:
            self._attr_extra_state_attributes["last_run"] = (
                status_entry.last_run.isoformat()
            )

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensors."""
    data = entry.runtime_data
    status_coordinator = PaperlessStatusCoordinator(hass, entry, data.client)
    await status_coordinator.async_config_entry_first_refresh()

    entities = []

    for description in SENSOR_DESCRIPTIONS:
        entity = PaperlessSensor(
            data,
            entry,
            description,
        )
        entities.append(entity)

    entities_status = []

    for description_status in STATUS_SENSOR_DESCRIPTION:
        entity_status = PaperlessStatusSensor(
            status_coordinator,
            data,
            entry,
            description_status,
        )
        entities_status.append(entity_status)

    async_add_entities(entities)
    async_add_entities(entities_status)
