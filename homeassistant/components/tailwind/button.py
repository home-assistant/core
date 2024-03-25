"""Button entity platform for Tailwind."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from gotailwind import Tailwind, TailwindError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TailwindDataUpdateCoordinator
from .entity import TailwindEntity


@dataclass(frozen=True, kw_only=True)
class TailwindButtonEntityDescription(ButtonEntityDescription):
    """Class describing Tailwind button entities."""

    press_fn: Callable[[Tailwind], Awaitable[Any]]


DESCRIPTIONS = [
    TailwindButtonEntityDescription(
        key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda tailwind: tailwind.identify(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tailwind button based on a config entry."""
    coordinator: TailwindDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TailwindButtonEntity(
            coordinator,
            description,
        )
        for description in DESCRIPTIONS
    )


class TailwindButtonEntity(TailwindEntity, ButtonEntity):
    """Representation of a Tailwind button entity."""

    entity_description: TailwindButtonEntityDescription

    async def async_press(self) -> None:
        """Trigger button press on the Tailwind device."""
        try:
            await self.entity_description.press_fn(self.coordinator.tailwind)
        except TailwindError as exc:
            raise HomeAssistantError(
                str(exc),
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from exc
