"""Support for Paperless-ngx sensors."""

from __future__ import annotations

from _collections_abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PaperlessConfigEntry, PaperlessData
from .const import (
    DIAGNOSIS_NAME_STORAGE_AVAILABLE,
    DIAGNOSIS_NAME_STORAGE_TOTAL,
    DOMAIN,
    SENSOR_NAME_DOCUMENT_COUNT,
    SENSOR_NAME_INBOX_COUNT,
)
from .entity import PaperlessEntity

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 2


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""


SENSOR_DESCRIPTIONS: tuple[PaperlessEntityDescription, ...] = (
    PaperlessEntityDescription(
        key=SENSOR_NAME_DOCUMENT_COUNT,
        translation_key=SENSOR_NAME_DOCUMENT_COUNT,
        icon="mdi:file-document-multiple",
        state_class=SensorStateClass.TOTAL,
    ),
    PaperlessEntityDescription(
        key=SENSOR_NAME_INBOX_COUNT,
        translation_key=SENSOR_NAME_INBOX_COUNT,
        icon="mdi:file-document-alert",
        state_class=SensorStateClass.TOTAL,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STORAGE_TOTAL,
        translation_key=DIAGNOSIS_NAME_STORAGE_TOTAL,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PaperlessEntityDescription(
        key=DIAGNOSIS_NAME_STORAGE_AVAILABLE,
        translation_key=DIAGNOSIS_NAME_STORAGE_AVAILABLE,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensor based on a config entry."""
    data = entry.runtime_data

    descriptions = {desc.key: desc for desc in SENSOR_DESCRIPTIONS}
    async_add_entities(
        [
            DocumentCountSensor(
                data, entry, description=descriptions[SENSOR_NAME_DOCUMENT_COUNT]
            ),
            InboxCountSensor(
                data, entry, description=descriptions[SENSOR_NAME_INBOX_COUNT]
            ),
            StorageTotalSensor(
                data, entry, description=descriptions[DIAGNOSIS_NAME_STORAGE_TOTAL]
            ),
            StorageAvailableSensor(
                data, entry, description=descriptions[DIAGNOSIS_NAME_STORAGE_AVAILABLE]
            ),
        ]
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
        self._attr_unique_id = (
            f"{DOMAIN}_{self}_{data.client.base_url}_sensor_{description.key}"
        )


class DocumentCountSensor(PaperlessSensor, SensorEntity):
    """Document count sensor."""

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        value = await self.client.documents.all()
        self._attr_native_value = len(value)


class InboxCountSensor(PaperlessSensor, SensorEntity):
    """Inbox count sensor."""

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        if len(self.inbox_tags) == 0:
            self._attr_native_value = 0
            return

        tag_ids = [str(tag.id) for tag in self.inbox_tags if tag.id is not None]

        if not tag_ids:
            self._attr_native_value = 0
            return

        tag_ids_str = ",".join(tag_ids)

        async with self.client.documents.reduce(tags__id__in=tag_ids_str) as documents:
            inbox_document_ids = await documents.all()

        self._attr_native_value = len(inbox_document_ids)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        if not self.inbox_tags:
            return None

        return {"inbox_tags": [tag.name for tag in self.inbox_tags]}


class StorageTotalSensor(PaperlessSensor, SensorEntity):
    """Document count sensor."""

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        status = await self.client.status()

        if status.storage is not None and status.storage.total is not None:
            self._attr_native_value = round(status.storage.total / (1024**3), 2)
            self._attr_available = True
        else:
            self._attr_native_value = None
            self._attr_available = False


class StorageAvailableSensor(PaperlessSensor, SensorEntity):
    """Document count sensor."""

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        status = await self.client.status()

        if status.storage is not None and status.storage.available is not None:
            self._attr_native_value = round(status.storage.available / (1024**3), 2)
            self._attr_available = True
        else:
            self._attr_native_value = None
            self._attr_available = False
