"""Support for Tile binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pytile.tile import Tile

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TileConfigEntry, TileCoordinator
from .entity import TileEntity


@dataclass(frozen=True, kw_only=True)
class TileBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Tile binary sensor entity."""

    is_on_fn: Callable[[Tile], bool]


ENTITIES: tuple[TileBinarySensorEntityDescription, ...] = (
    TileBinarySensorEntityDescription(
        key="lost",
        translation_key="lost",
        is_on_fn=lambda tile: tile.lost,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TileConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tile binary sensors."""

    async_add_entities(
        TileBinarySensor(coordinator, entity_description)
        for entity_description in ENTITIES
        for coordinator in entry.runtime_data.values()
    )


class TileBinarySensor(TileEntity, BinarySensorEntity):
    """Representation of a Tile binary sensor."""

    entity_description: TileBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TileCoordinator,
        description: TileBinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.username}_{self._tile.uuid}_{description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._tile)
