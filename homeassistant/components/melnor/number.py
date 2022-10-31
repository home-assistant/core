"""Number support for Melnor Bluetooth water timer."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from melnor_bluetooth.device import Valve

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import (
    MelnorDataUpdateCoordinator,
    MelnorZoneEntity,
    get_entities_for_valves,
)


@dataclass
class MelnorZoneNumberEntityDescriptionMixin:
    """Mixin for required keys."""

    set_num_fn: Callable[[Valve, int], Coroutine[Any, Any, None]]
    state_fn: Callable[[Valve], Any]


@dataclass
class MelnorZoneNumberEntityDescription(
    NumberEntityDescription, MelnorZoneNumberEntityDescriptionMixin
):
    """Describes Melnor number entity."""


ZONE_ENTITY_DESCRIPTIONS: list[MelnorZoneNumberEntityDescription] = [
    MelnorZoneNumberEntityDescription(
        entity_category=EntityCategory.CONFIG,
        native_max_value=360,
        native_min_value=1,
        icon="mdi:timer-cog-outline",
        key="manual_minutes",
        name="Manual Minutes",
        set_num_fn=lambda valve, value: valve.set_manual_watering_minutes(value),
        state_fn=lambda valve: valve.manual_watering_minutes,
    )
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
        return self._valve.manual_watering_minutes

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.set_num_fn(self._valve, int(value))
        self._async_write_ha_state()
