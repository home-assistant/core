"""Number support for Melnor Bluetooth water timer."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from melnor_bluetooth.device import Valve

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MelnorDataUpdateCoordinator
from .models import MelnorZoneEntity, get_entities_for_valves


@dataclass(frozen=True, kw_only=True)
class MelnorZoneNumberEntityDescription(NumberEntityDescription):
    """Describes Melnor number entity."""

    set_num_fn: Callable[[Valve, int], Coroutine[Any, Any, None]]
    state_fn: Callable[[Valve], Any]


ZONE_ENTITY_DESCRIPTIONS: list[MelnorZoneNumberEntityDescription] = [
    MelnorZoneNumberEntityDescription(
        entity_category=EntityCategory.CONFIG,
        native_max_value=360,
        native_min_value=1,
        key="manual_minutes",
        translation_key="manual_minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        set_num_fn=lambda valve, value: valve.set_manual_watering_minutes(value),
        state_fn=lambda valve: valve.manual_watering_minutes,
    ),
    MelnorZoneNumberEntityDescription(
        entity_category=EntityCategory.CONFIG,
        native_max_value=168,
        native_min_value=1,
        key="frequency_interval_hours",
        translation_key="frequency_interval_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        set_num_fn=lambda valve, value: valve.set_frequency_interval_hours(value),
        state_fn=lambda valve: valve.frequency.interval_hours,
    ),
    MelnorZoneNumberEntityDescription(
        entity_category=EntityCategory.CONFIG,
        native_max_value=360,
        native_min_value=1,
        key="frequency_duration_minutes",
        translation_key="frequency_duration_minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        set_num_fn=lambda valve, value: valve.set_frequency_duration_minutes(value),
        state_fn=lambda valve: valve.frequency.duration_minutes,
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
            lambda valve, description: MelnorZoneNumber(
                coordinator, description, valve
            ),
        )
    )


class MelnorZoneNumber(MelnorZoneEntity, NumberEntity):
    """A number implementation for a melnor device."""

    entity_description: MelnorZoneNumberEntityDescription
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        entity_description: MelnorZoneNumberEntityDescription,
        valve: Valve,
    ) -> None:
        """Initialize a number for a melnor device."""
        super().__init__(coordinator, entity_description, valve)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.state_fn(self._valve)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.set_num_fn(self._valve, int(value))
        self._async_write_ha_state()
