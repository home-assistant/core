"""Support for Renault button entities."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .renault_entities import RenaultEntity
from .renault_hub import RenaultHub


@dataclass
class RenaultButtonRequiredKeysMixin:
    """Mixin for required keys."""

    async_press: Callable[[RenaultButtonEntity], Awaitable]


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


async def _start_charge(entity: RenaultButtonEntity) -> None:
    """Start charge on the vehicle."""
    await entity.vehicle.vehicle.set_charge_start()


async def _start_air_conditioner(entity: RenaultButtonEntity) -> None:
    """Start air conditioner on the vehicle."""
    await entity.vehicle.vehicle.set_ac_start(21, None)


BUTTON_TYPES: tuple[RenaultButtonEntityDescription, ...] = (
    RenaultButtonEntityDescription(
        async_press=_start_air_conditioner,
        key="start_air_conditioner",
        icon="mdi:air-conditioner",
        name="Start air conditioner",
    ),
    RenaultButtonEntityDescription(
        async_press=_start_charge,
        key="start_charge",
        icon="mdi:ev-station",
        name="Start charge",
        requires_electricity=True,
    ),
)
