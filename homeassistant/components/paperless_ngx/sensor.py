"""Support for Paperless-ngx sensors."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pypaperless.models.common import StatusType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
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
from .entity import PaperlessEntity

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 2


ReturnValue = StatusType | int | float | None


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: (
        Callable[[PaperlessData], Coroutine[Any, Any, tuple[ReturnValue, str | None]]]
        | None
    ) = None


async def get_document_count(data: PaperlessData) -> tuple[int | None, str | None]:
    """Get the number of documents in the system."""
    documents = await data.client.documents.all()
    return len(documents), None


async def get_inbox_count(data: PaperlessData) -> tuple[int | None, str | None]:
    """Get the number of documents in the inbox."""
    if not data.inbox_tags:
        return 0, None
    tag_ids = [str(tag.id) for tag in data.inbox_tags if tag.id is not None]
    if not tag_ids:
        return 0, None
    tag_ids_str = ",".join(tag_ids)
    async with data.client.documents.reduce(tags__id__in=tag_ids_str) as docs:
        inbox_docs = await docs.all()
    return len(inbox_docs), None


async def get_storage_total(data: PaperlessData) -> tuple[float | None, str | None]:
    """Get total storage in gigabytes."""
    status = await data.client.status()
    if status.storage and status.storage.total is not None:
        return round(status.storage.total / (1024**3), 2), None
    return None, None


async def get_storage_available(data: PaperlessData) -> tuple[float | None, str | None]:
    """Get available storage in gigabytes."""
    status = await data.client.status()
    if status.storage and status.storage.available is not None:
        return round(status.storage.available / (1024**3), 2), None
    return None, None


async def get_status_database(
    data: PaperlessData,
) -> tuple[StatusType | None, str | None]:
    """Get database status."""
    status = await data.client.status()
    database_status = status.database.status if status.database else None
    database_error = status.database.error if status.database else None

    if database_status == StatusType.ERROR and database_error:
        return database_status, database_error
    return database_status, None


async def get_status_redis(data: PaperlessData) -> tuple[StatusType | None, str | None]:
    """Get Redis status."""
    status = await data.client.status()
    redis_status = status.tasks.redis_status if status.tasks else None
    redis_error = status.tasks.redis_error if status.tasks else None

    if redis_status == StatusType.ERROR and redis_error:
        return redis_status, redis_error
    return redis_status, None


async def get_status_celery(
    data: PaperlessData,
) -> tuple[StatusType | None, str | None]:
    """Get Celery status."""
    status = await data.client.status()
    celery_status = status.tasks.celery_status if status.tasks else None
    return celery_status, None


async def get_status_index(data: PaperlessData) -> tuple[StatusType | None, str | None]:
    """Get index status."""
    status = await data.client.status()
    index_status = status.tasks.index_status if status.tasks else None
    index_error = status.tasks.index_error if status.tasks else None

    if index_status == StatusType.ERROR and index_error:
        return index_status, index_error
    return index_status, None


async def get_status_classifier(
    data: PaperlessData,
) -> tuple[StatusType | None, str | None]:
    """Get classifier status."""
    status = await data.client.status()
    classifier_status = status.tasks.classifier_status if status.tasks else None
    classifier_error = status.tasks.classifier_error if status.tasks else None

    if classifier_status == StatusType.ERROR and classifier_error:
        return classifier_status, classifier_error
    return classifier_status, None


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
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STORAGE_TOTAL,
        translation_key=DIAGNOSIS_NAME_STORAGE_TOTAL,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_storage_total,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STORAGE_AVAILABLE,
        translation_key=DIAGNOSIS_NAME_STORAGE_AVAILABLE,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_storage_available,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_DATABASE,
        translation_key=DIAGNOSIS_NAME_STATUS_DATABASE,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_status_database,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_REDIS,
        translation_key=DIAGNOSIS_NAME_STATUS_REDIS,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_status_redis,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_CELERY,
        translation_key=DIAGNOSIS_NAME_STATUS_CELERY,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_status_celery,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_INDEX,
        translation_key=DIAGNOSIS_NAME_STATUS_INDEX,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_status_index,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STATUS_CLASSIFIER,
        translation_key=DIAGNOSIS_NAME_STATUS_CLASSIFIER,
        icon="mdi:check-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in StatusType],
        value_fn=get_status_classifier,
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
        super().__init__(data, entry)
        self.entity_description = description
        self.data = data
        self._attr_unique_id = f"{DOMAIN}_{self}_{data.client.base_url}_sensor_{description.key}_{entry.entry_id}"

    async def _paperless_update(self) -> None:
        value_fn = self.entity_description.value_fn
        if value_fn is None:
            raise NotImplementedError

        value = await value_fn(self.data)

        if isinstance(value, tuple):
            status, error = value
        else:
            status, error = value, None

        if isinstance(status, StatusType):
            self._attr_native_value = status.value
        else:
            self._attr_native_value = status

        self._attr_extra_state_attributes = {}
        if error:
            self._attr_extra_state_attributes["error_message"] = error


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensors."""
    data = entry.runtime_data

    entities = [
        PaperlessSensor(data, entry, description) for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)
