"""Support for Renault button entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultEntity

# Coordinator is used to centralize the data updates
# but renault servers are unreliable and it's safer to queue action calls
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RenaultButtonEntityDescription(ButtonEntityDescription):
    """Class describing Renault button entities."""

    async_press: Callable[[RenaultButtonEntity], Coroutine[Any, Any, Any]]
    requires_electricity: bool = False


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultButtonEntity] = [
        RenaultButtonEntity(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in BUTTON_TYPES
        if not description.requires_electricity or vehicle.details.uses_electricity()
    ]
    async_add_entities(entities)


class RenaultButtonEntity(RenaultEntity, ButtonEntity):
    """Mixin for button specific attributes."""

    entity_description: RenaultButtonEntityDescription

    async def async_press(self) -> None:
        """Process the button press."""
        await self.entity_description.async_press(self)


BUTTON_TYPES: tuple[RenaultButtonEntityDescription, ...] = (
    RenaultButtonEntityDescription(
        async_press=lambda x: x.vehicle.set_ac_start(21, None),
        key="start_air_conditioner",
        translation_key="start_air_conditioner",
    ),
    RenaultButtonEntityDescription(
        async_press=lambda x: x.vehicle.set_charge_start(),
        key="start_charge",
        requires_electricity=True,
        translation_key="start_charge",
    ),
    RenaultButtonEntityDescription(
        async_press=lambda x: x.vehicle.set_charge_stop(),
        key="stop_charge",
        requires_electricity=True,
        translation_key="stop_charge",
    ),
)
