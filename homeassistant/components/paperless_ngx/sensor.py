"""Update platform for Paperless-ngx."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PaperlessConfigEntry, PaperlessCoordinator, PaperlessData
from .entity import PaperlessEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PaperlessEntityDescription(SensorEntityDescription):
    """Describes Paperless-ngx sensor entity."""

    value_fn: Callable[[PaperlessData], int | None]


SENSOR_DESCRIPTIONS: tuple[PaperlessEntityDescription, ...] = (
    PaperlessEntityDescription(
        key="documents_total",
        translation_key="documents_total",
        state_class=SensorStateClass.TOTAL,
        value_fn=(
            lambda data: data.statistic.documents_total if data.statistic else None
        ),
    ),
    PaperlessEntityDescription(
        key="documents_inbox",
        translation_key="documents_inbox",
        state_class=SensorStateClass.TOTAL,
        value_fn=(
            lambda data: data.statistic.documents_inbox if data.statistic else None
        ),
    ),
    PaperlessEntityDescription(
        key="characters_count",
        translation_key="characters_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=(
            lambda data: data.statistic.character_count if data.statistic else None
        ),
    ),
    PaperlessEntityDescription(
        key="tag_count",
        translation_key="tag_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.statistic.tag_count if data.statistic else None,
    ),
    PaperlessEntityDescription(
        key="correspondent_count",
        translation_key="correspondent_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=(
            lambda data: data.statistic.correspondent_count if data.statistic else None
        ),
    ),
    PaperlessEntityDescription(
        key="document_type_count",
        translation_key="document_type_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=(
            lambda data: data.statistic.document_type_count if data.statistic else None
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
        PaperlessSensor(
            entry=entry,
            coordinator=entry.runtime_data,
            description=description,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class PaperlessSensor(PaperlessEntity, SensorEntity):
    """Defines a Paperless-ngx sensor entity."""

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
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
