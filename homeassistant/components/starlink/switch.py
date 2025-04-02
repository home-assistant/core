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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StarlinkConfigEntry, StarlinkData, StarlinkUpdateCoordinator
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: StarlinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all binary sensors for this entry."""
    async_add_entities(
        StarlinkSwitchEntity(config_entry.runtime_data, description)
        for description in SWITCHES
    )


@dataclass(frozen=True, kw_only=True)
class StarlinkSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Starlink switch entity."""

    value_fn: Callable[[StarlinkData], bool | None]
    turn_on_fn: Callable[[StarlinkUpdateCoordinator], Awaitable[None]]
    turn_off_fn: Callable[[StarlinkUpdateCoordinator], Awaitable[None]]


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
    ),
    StarlinkSwitchEntityDescription(
        key="sleep_schedule",
        translation_key="sleep_schedule",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda data: data.sleep[2],
        turn_on_fn=lambda coordinator: coordinator.async_set_sleep_schedule_enabled(
            True
        ),
        turn_off_fn=lambda coordinator: coordinator.async_set_sleep_schedule_enabled(
            False
        ),
    ),
]
