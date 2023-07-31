"""Support for Renault button entities."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import RenaultEntity
from .renault_hub import RenaultHub


@dataclass
class RenaultButtonRequiredKeysMixin:
    """Mixin for required keys."""

    async_press: Callable[[RenaultButtonEntity], Coroutine[Any, Any, Any]]


@dataclass
class RenaultButtonEntityDescription(
    ButtonEntityDescription, RenaultButtonRequiredKeysMixin
):
    """Class describing Renault button entities."""

    requires_electricity: bool = False


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[RenaultButtonEntity] = [
        RenaultButtonEntity(vehicle, description)
        for vehicle in proxy.vehicles.values()
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
        icon="mdi:air-conditioner",
        translation_key="start_air_conditioner",
    ),
    RenaultButtonEntityDescription(
        async_press=lambda x: x.vehicle.set_charge_start(),
        key="start_charge",
        icon="mdi:ev-station",
        requires_electricity=True,
        translation_key="start_charge",
    ),
    RenaultButtonEntityDescription(
        async_press=lambda x: x.vehicle.set_charge_stop(),
        key="stop_charge",
        icon="mdi:ev-station",
        requires_electricity=True,
        translation_key="stop_charge",
    ),
)
