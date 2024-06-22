"""Number support for Melnor Bluetooth water timer."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import Any

from melnor_bluetooth.device import Valve

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MelnorDataUpdateCoordinator
from .models import MelnorZoneEntity, get_entities_for_valves


@dataclass(frozen=True, kw_only=True)
class MelnorZoneTimeEntityDescription(TimeEntityDescription):
    """Describes Melnor number entity."""

    set_time_fn: Callable[[Valve, time], Coroutine[Any, Any, None]]
    state_fn: Callable[[Valve], Any]


ZONE_ENTITY_DESCRIPTIONS: list[MelnorZoneTimeEntityDescription] = [
    MelnorZoneTimeEntityDescription(
        entity_category=EntityCategory.CONFIG,
        key="frequency_start_time",
        translation_key="frequency_start_time",
        set_time_fn=lambda valve, value: valve.set_frequency_start_time(value),
        state_fn=lambda valve: valve.frequency.start_time,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        get_entities_for_valves(
            coordinator,
            ZONE_ENTITY_DESCRIPTIONS,
            lambda valve, description: MelnorZoneTime(coordinator, description, valve),
        )
    )


class MelnorZoneTime(MelnorZoneEntity, TimeEntity):
    """A time implementation for a melnor device."""

    entity_description: MelnorZoneTimeEntityDescription

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        entity_description: MelnorZoneTimeEntityDescription,
        valve: Valve,
    ) -> None:
        """Initialize a number for a melnor device."""
        super().__init__(coordinator, entity_description, valve)

    @property
    def native_value(self) -> time | None:
        """Return the current value."""
        return self.entity_description.state_fn(self._valve)

    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        await self.entity_description.set_time_fn(self._valve, value)
