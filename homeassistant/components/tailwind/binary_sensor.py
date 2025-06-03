"""Binary sensor entity platform for Tailwind."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gotailwind import TailwindDoor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TailwindConfigEntry
from .entity import TailwindDoorEntity


@dataclass(kw_only=True, frozen=True)
class TailwindDoorBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Tailwind door binary sensor entities."""

    is_on_fn: Callable[[TailwindDoor], bool]


DESCRIPTIONS: tuple[TailwindDoorBinarySensorEntityDescription, ...] = (
    TailwindDoorBinarySensorEntityDescription(
        key="locked_out",
        translation_key="operational_problem",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda door: door.locked_out,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TailwindConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tailwind binary sensor based on a config entry."""
    async_add_entities(
        TailwindDoorBinarySensorEntity(entry.runtime_data, door_id, description)
        for description in DESCRIPTIONS
        for door_id in entry.runtime_data.data.doors
    )


class TailwindDoorBinarySensorEntity(TailwindDoorEntity, BinarySensorEntity):
    """Representation of a Tailwind door binary sensor entity."""

    entity_description: TailwindDoorBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(
            self.coordinator.data.doors[self.door_id]
        )
