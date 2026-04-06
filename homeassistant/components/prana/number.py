"""Number platform for Prana integration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PranaConfigEntry, PranaCoordinator
from .entity import PranaBaseEntity

PARALLEL_UPDATES = 1


class PranaNumberType(StrEnum):
    """Enumerates Prana number types exposed by the device API."""

    DISPLAY_BRIGHTNESS = "display_brightness"


@dataclass(frozen=True, kw_only=True)
class PranaNumberEntityDescription(NumberEntityDescription):
    """Description of a Prana number entity."""

    key: PranaNumberType
    value_fn: Callable[[PranaCoordinator], float | None]
    set_value_fn: Callable[[Any, float], Any]


ENTITIES: tuple[PranaNumberEntityDescription, ...] = (
    PranaNumberEntityDescription(
        key=PranaNumberType.DISPLAY_BRIGHTNESS,
        translation_key="display_brightness",
        native_min_value=0,
        native_max_value=6,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda coord: coord.data.brightness,
        set_value_fn=lambda api, val: api.set_brightness(
            0 if val == 0 else 2 ** (int(val) - 1)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PranaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana number entities from a config entry."""
    async_add_entities(
        PranaNumber(entry.runtime_data, entity_description)
        for entity_description in ENTITIES
    )


class PranaNumber(PranaBaseEntity, NumberEntity):
    """Representation of a Prana number entity."""

    entity_description: PranaNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the entity value."""
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.set_value_fn(self.coordinator.api_client, value)
        await self.coordinator.async_refresh()
