"""Contains switches exposed by the Starlink integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import StarlinkData, StarlinkUpdateCoordinator
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all binary sensors for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StarlinkSwitchEntity(coordinator, description) for description in SWITCHES
    )


@dataclass
class StarlinkSwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[StarlinkData], bool | None]
    turn_on_fn: Callable[[StarlinkUpdateCoordinator], Awaitable[None]]
    turn_off_fn: Callable[[StarlinkUpdateCoordinator], Awaitable[None]]


@dataclass
class StarlinkSwitchEntityDescription(
    SwitchEntityDescription, StarlinkSwitchEntityDescriptionMixin
):
    """Describes a Starlink switch entity."""


class StarlinkSwitchEntity(StarlinkEntity, SwitchEntity):
    """A SwitchEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        return await self.entity_description.turn_on_fn(self.coordinator)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        return await self.entity_description.turn_off_fn(self.coordinator)


SWITCHES = [
    StarlinkSwitchEntityDescription(
        key="stowed",
        translation_key="stowed",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda data: data.status["state"] == "STOWED",
        turn_on_fn=lambda coordinator: coordinator.async_stow_starlink(True),
        turn_off_fn=lambda coordinator: coordinator.async_stow_starlink(False),
    )
]
