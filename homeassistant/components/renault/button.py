"""Support for Renault button entities."""
from __future__ import annotations

import asyncio
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
    cooldown: int


@dataclass
class RenaultButtonEntityDescription(
    ButtonEntityDescription, RenaultButtonRequiredKeysMixin
):
    """Class describing Renault button entities."""


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
    ]
    async_add_entities(entities)


class RenaultButtonEntity(RenaultEntity, ButtonEntity):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultButtonEntityDescription

    async def async_press(self) -> None:
        """Send out a persistent notification."""
        await self.entity_description.async_press(self)
        if self.entity_description.cooldown > 0:
            self._attr_available = False
            await asyncio.sleep(self.entity_description.cooldown)
            self._attr_available = True


async def _start_charge(entity: RenaultButtonEntity) -> None:
    """Return the icon of this entity."""
    entity.hass.components.persistent_notification.async_create(
        "Button pressed", title="set_charge_start"
    )
    await entity.vehicle.vehicle.set_charge_start()


async def _start_air_conditioner(entity: RenaultButtonEntity) -> None:
    """Return the icon of this entity."""
    entity.hass.components.persistent_notification.async_create(
        "Button pressed", title="set_ac_start"
    )
    await entity.vehicle.vehicle.set_ac_start(21)


BUTTON_TYPES: tuple[RenaultButtonEntityDescription, ...] = (
    RenaultButtonEntityDescription(
        async_press=_start_air_conditioner,
        cooldown=30,
        key="start_air_conditioner",
        icon="mdi:air-conditioner",
        name="Start Air Conditioner",
    ),
    RenaultButtonEntityDescription(
        async_press=_start_charge,
        cooldown=30,
        key="start_charge",
        icon="mdi:ev-station",
        name="Start Charge",
    ),
)
