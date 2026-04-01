"""Arcam binary sensors for incoming stream info."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arcam.fmj.state import State

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ArcamFmjConfigEntry
from .entity import ArcamFmjEntity


@dataclass(frozen=True, kw_only=True)
class ArcamFmjBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Arcam FMJ binary sensor entity."""

    value_fn: Callable[[State], bool | None]


BINARY_SENSORS: tuple[ArcamFmjBinarySensorEntityDescription, ...] = (
    ArcamFmjBinarySensorEntityDescription(
        key="incoming_video_interlaced",
        translation_key="incoming_video_interlaced",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: (
            vp.interlaced
            if (vp := state.get_incoming_video_parameters()) is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ binary sensors from a config entry."""
    coordinators = config_entry.runtime_data.coordinators

    entities: list[ArcamFmjBinarySensorEntity] = []
    for coordinator in coordinators.values():
        entities.extend(
            ArcamFmjBinarySensorEntity(coordinator, description)
            for description in BINARY_SENSORS
        )
    async_add_entities(entities)


class ArcamFmjBinarySensorEntity(ArcamFmjEntity, BinarySensorEntity):
    """Representation of an Arcam FMJ binary sensor."""

    entity_description: ArcamFmjBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor value."""
        return self.entity_description.value_fn(self.coordinator.state)
