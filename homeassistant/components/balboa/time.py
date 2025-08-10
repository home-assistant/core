"""Support for Balboa times."""

from __future__ import annotations

from datetime import time
import itertools
from typing import Any

from pybalboa import SpaClient

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BalboaConfigEntry
from .entity import BalboaEntity

FILTER_CYCLE = "filter_cycle_"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BalboaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the spa's times."""
    spa = entry.runtime_data
    async_add_entities(
        BalboaTimeEntity(spa, index, period)
        for index, period in itertools.product((1, 2), ("start", "end"))
    )


class BalboaTimeEntity(BalboaEntity, TimeEntity):
    """Representation of a Balboa time entity."""

    entity_category = EntityCategory.CONFIG

    def __init__(self, spa: SpaClient, index: int, period: str) -> None:
        """Initialize a Balboa time entity."""
        super().__init__(spa, f"{FILTER_CYCLE}{index}_{period}")
        self.index = index
        self.period = period
        self._attr_translation_key = f"{FILTER_CYCLE}{period}"
        self._attr_translation_placeholders = {"index": str(index)}

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return getattr(self._client, f"{FILTER_CYCLE}{self.index}_{self.period}")

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        args: dict[str, Any] = {self.period: value}
        await self._client.configure_filter_cycle(self.index, **args)
