"""Sensor platform for Paperless-ngx."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pypaperless.models import Statistic, Status
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
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_conversion import InformationConverter

from .coordinator import (
    PaperlessConfigEntry,
    PaperlessCoordinator,
    PaperlessStatisticCoordinator,
    PaperlessStatusCoordinator,
)
from .entity import PaperlessEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription[DataT](SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: Callable[[DataT], StateType]


SENSOR_STATISTICS: tuple[PaperlessEntityDescription[Statistic], ...] = (
    PaperlessEntityDescription[Statistic](
        key="documents_total",
        translation_key="documents_total",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.documents_total,
    ),
    PaperlessEntityDescription[Statistic](
        key="documents_inbox",
        translation_key="documents_inbox",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.documents_inbox,
    ),
    PaperlessEntityDescription[Statistic](
        key="characters_count",
        translation_key="characters_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.character_count,
    ),
    PaperlessEntityDescription[Statistic](
        key="tag_count",
        translation_key="tag_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tag_count,
    ),
    PaperlessEntityDescription[Statistic](
        key="correspondent_count",
        translation_key="correspondent_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.correspondent_count,
    ),
    PaperlessEntityDescription[Statistic](
        key="document_type_count",
        translation_key="document_type_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.document_type_count,
    ),
)

SENSOR_STATUS: tuple[PaperlessEntityDescription[Status], ...] = (
    PaperlessEntityDescription[Status](
        key="storage_total",
        translation_key="storage_total",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=(
            lambda data: round(
                InformationConverter().convert(
                    data.storage.total,
                    UnitOfInformation.BYTES,
                    UnitOfInformation.GIGABYTES,
                ),
                2,
            )
            if data.storage is not None and data.storage.total is not None
            else None
        ),
    ),
    PaperlessEntityDescription[Status](
        key="storage_available",
        translation_key="storage_available",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=(
            lambda data: round(
                InformationConverter().convert(
                    data.storage.available,
                    UnitOfInformation.BYTES,
                    UnitOfInformation.GIGABYTES,
                ),
                2,
            )
            if data.storage is not None and data.storage.available is not None
            else None
        ),
    ),
    PaperlessEntityDescription[Status](
        key="database_status",
        translation_key="database_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            item.value.lower() for item in StatusType if item != StatusType.UNKNOWN
        ],
        value_fn=(
            lambda data: data.database.status.value.lower()
            if (
                data.database is not None
                and data.database.status is not None
                and data.database.status != StatusType.UNKNOWN
            )
            else None
        ),
    ),
    PaperlessEntityDescription[Status](
        key="index_status",
        translation_key="index_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            item.value.lower() for item in StatusType if item != StatusType.UNKNOWN
        ],
        value_fn=(
            lambda data: data.tasks.index_status.value.lower()
            if (
                data.tasks is not None
                and data.tasks.index_status is not None
                and data.tasks.index_status != StatusType.UNKNOWN
            )
            else None
        ),
    ),
    PaperlessEntityDescription[Status](
        key="classifier_status",
        translation_key="classifier_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            item.value.lower() for item in StatusType if item != StatusType.UNKNOWN
        ],
        value_fn=(
            lambda data: data.tasks.classifier_status.value.lower()
            if (
                data.tasks is not None
                and data.tasks.classifier_status is not None
                and data.tasks.classifier_status != StatusType.UNKNOWN
            )
            else None
        ),
    ),
    PaperlessEntityDescription[Status](
        key="celery_status",
        translation_key="celery_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            item.value.lower() for item in StatusType if item != StatusType.UNKNOWN
        ],
        value_fn=(
            lambda data: data.tasks.celery_status.value.lower()
            if (
                data.tasks is not None
                and data.tasks.celery_status is not None
                and data.tasks.celery_status != StatusType.UNKNOWN
            )
            else None
        ),
    ),
    PaperlessEntityDescription[Status](
        key="redis_status",
        translation_key="redis_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            item.value.lower() for item in StatusType if item != StatusType.UNKNOWN
        ],
        value_fn=(
            lambda data: data.tasks.redis_status.value.lower()
            if (
                data.tasks is not None
                and data.tasks.redis_status is not None
                and data.tasks.redis_status != StatusType.UNKNOWN
            )
            else None
        ),
    ),
    PaperlessEntityDescription[Status](
        key="sanity_check_status",
        translation_key="sanity_check_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            item.value.lower() for item in StatusType if item != StatusType.UNKNOWN
        ],
        value_fn=(
            lambda data: data.tasks.sanity_check_status.value.lower()
            if (
                data.tasks is not None
                and data.tasks.sanity_check_status is not None
                and data.tasks.sanity_check_status != StatusType.UNKNOWN
            )
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensors."""

    entities: list[PaperlessSensor] = []

    entities += [
        PaperlessSensor[PaperlessStatisticCoordinator](
            coordinator=entry.runtime_data.statistics,
            description=description,
        )
        for description in SENSOR_STATISTICS
    ]

    entities += [
        PaperlessSensor[PaperlessStatusCoordinator](
            coordinator=entry.runtime_data.status,
            description=description,
        )
        for description in SENSOR_STATUS
    ]

    async_add_entities(entities)


class PaperlessSensor[CoordinatorT: PaperlessCoordinator](
    PaperlessEntity[CoordinatorT], SensorEntity
):
    """Defines a Paperless-ngx sensor entity."""

    entity_description: PaperlessEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
