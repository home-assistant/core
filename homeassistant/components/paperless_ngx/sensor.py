"""Sensor platform for Paperless-ngx."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pypaperless.models import Statistic

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PaperlessConfigEntry
from .entity import PaperlessEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: Callable[[Statistic], int | None]


SENSOR_DESCRIPTIONS: tuple[PaperlessEntityDescription, ...] = (
    PaperlessEntityDescription(
        key="documents_total",
        translation_key="documents_total",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.documents_total,
    ),
    PaperlessEntityDescription(
        key="documents_inbox",
        translation_key="documents_inbox",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.documents_inbox,
    ),
    PaperlessEntityDescription(
        key="characters_count",
        translation_key="characters_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.character_count,
    ),
    PaperlessEntityDescription(
        key="tag_count",
        translation_key="tag_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tag_count,
    ),
    PaperlessEntityDescription(
        key="correspondent_count",
        translation_key="correspondent_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.correspondent_count,
    ),
    PaperlessEntityDescription(
        key="document_type_count",
        translation_key="document_type_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.document_type_count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx sensors."""
    async_add_entities(
        PaperlessSensor(
            coordinator=entry.runtime_data,
            description=sensor_description,
        )
        for sensor_description in SENSOR_DESCRIPTIONS
    )


class PaperlessSensor(PaperlessEntity, SensorEntity):
    """Defines a Paperless-ngx sensor entity."""

    entity_description: PaperlessEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the current value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
