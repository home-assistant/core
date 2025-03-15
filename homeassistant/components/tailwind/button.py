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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import TailwindConfigEntry
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
    entry: TailwindConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tailwind button based on a config entry."""
    async_add_entities(
        TailwindButtonEntity(
            entry.runtime_data,
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
