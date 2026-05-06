"""Support for Fumis button entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fumis import Fumis

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FumisConfigEntry, FumisDataUpdateCoordinator
from .entity import FumisEntity
from .helpers import fumis_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class FumisButtonEntityDescription(ButtonEntityDescription):
    """Describes a Fumis button entity."""

    press_fn: Callable[[Fumis], Awaitable[Any]]


BUTTONS: tuple[FumisButtonEntityDescription, ...] = (
    FumisButtonEntityDescription(
        key="sync_clock",
        translation_key="sync_clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda client: client.set_clock(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FumisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fumis button entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        FumisButtonEntity(coordinator=coordinator, description=description)
        for description in BUTTONS
    )


class FumisButtonEntity(FumisEntity, ButtonEntity):
    """Defines a Fumis button entity."""

    entity_description: FumisButtonEntityDescription

    def __init__(
        self,
        coordinator: FumisDataUpdateCoordinator,
        description: FumisButtonEntityDescription,
    ) -> None:
        """Initialize the Fumis button entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @fumis_exception_handler
    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator.client)
