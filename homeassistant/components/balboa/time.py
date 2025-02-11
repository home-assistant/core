"""Support for Balboa times."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import time

from pybalboa import SpaClient

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BalboaConfigEntry
from .entity import BalboaEntity


@dataclass(frozen=True, kw_only=True)
class BalboaTimeEntityDescription(TimeEntityDescription):
    """A class that describes Balboa time entities."""

    set_fn: Callable[[SpaClient, time], Awaitable[None]]
    value_fn: Callable[[SpaClient], time | None]


TIME_DESCRIPTIONS = (
    BalboaTimeEntityDescription(
        key="filter_cycle_1_start",
        entity_category=EntityCategory.CONFIG,
        translation_key="filter_cycle_start",
        translation_placeholders={"index": "1"},
        set_fn=lambda spa, start: spa.configure_filter_cycle(1, start=start),
        value_fn=lambda spa: spa.filter_cycle_1_start,
    ),
    BalboaTimeEntityDescription(
        key="filter_cycle_1_end",
        entity_category=EntityCategory.CONFIG,
        translation_key="filter_cycle_end",
        translation_placeholders={"index": "1"},
        set_fn=lambda spa, end: spa.configure_filter_cycle(1, end=end),
        value_fn=lambda spa: spa.filter_cycle_1_end,
    ),
    BalboaTimeEntityDescription(
        key="filter_cycle_2_start",
        entity_category=EntityCategory.CONFIG,
        translation_key="filter_cycle_start",
        translation_placeholders={"index": "2"},
        set_fn=lambda spa, start: spa.configure_filter_cycle(2, start=start),
        value_fn=lambda spa: spa.filter_cycle_2_start,
    ),
    BalboaTimeEntityDescription(
        key="filter_cycle_2_end",
        entity_category=EntityCategory.CONFIG,
        translation_key="filter_cycle_end",
        translation_placeholders={"index": "2"},
        set_fn=lambda spa, end: spa.configure_filter_cycle(2, end=end),
        value_fn=lambda spa: spa.filter_cycle_2_end,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BalboaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the spa's times."""
    spa = entry.runtime_data
    async_add_entities(
        BalboaTimeEntity(spa, description) for description in TIME_DESCRIPTIONS
    )


class BalboaTimeEntity(BalboaEntity, TimeEntity):
    """Representation of a Balboa time entity."""

    entity_description: BalboaTimeEntityDescription

    def __init__(
        self, spa: SpaClient, description: BalboaTimeEntityDescription
    ) -> None:
        """Initialize a Balboa time entity."""
        super().__init__(spa, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.value_fn(self._client)

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        await self.entity_description.set_fn(self._client, value)
