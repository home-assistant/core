"""Contains buttons exposed by the Starlink integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StarlinkConfigEntry, StarlinkUpdateCoordinator
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: StarlinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all binary sensors for this entry."""
    async_add_entities(
        StarlinkButtonEntity(config_entry.runtime_data, description)
        for description in BUTTONS
    )


@dataclass(frozen=True, kw_only=True)
class StarlinkButtonEntityDescription(ButtonEntityDescription):
    """Describes a Starlink button entity."""

    press_fn: Callable[[StarlinkUpdateCoordinator], Awaitable[None]]


class StarlinkButtonEntity(StarlinkEntity, ButtonEntity):
    """A ButtonEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        return await self.entity_description.press_fn(self.coordinator)


BUTTONS = [
    StarlinkButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda coordinator: coordinator.async_reboot_starlink(),
    )
]
