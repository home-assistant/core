"""Support for Peblar selects."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from peblar import Peblar, PeblarUserConfiguration, SmartChargingMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PeblarConfigEntry, PeblarUserConfigurationDataUpdateCoordinator
from .entity import PeblarEntity
from .helpers import peblar_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PeblarSelectEntityDescription(SelectEntityDescription):
    """Class describing Peblar select entities."""

    current_fn: Callable[[PeblarUserConfiguration], str | None]
    select_fn: Callable[[Peblar, str], Awaitable[Any]]


DESCRIPTIONS = [
    PeblarSelectEntityDescription(
        key="smart_charging",
        translation_key="smart_charging",
        entity_category=EntityCategory.CONFIG,
        options=[
            "default",
            "fast_solar",
            "pure_solar",
            "scheduled",
            "smart_solar",
        ],
        current_fn=lambda x: x.smart_charging.value if x.smart_charging else None,
        select_fn=lambda x, mode: x.smart_charging(SmartChargingMode(mode)),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar select based on a config entry."""
    async_add_entities(
        PeblarSelectEntity(
            entry=entry,
            coordinator=entry.runtime_data.user_configuration_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarSelectEntity(
    PeblarEntity[PeblarUserConfigurationDataUpdateCoordinator],
    SelectEntity,
):
    """Defines a Peblar select entity."""

    entity_description: PeblarSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.data)

    @peblar_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.coordinator.peblar, option)
        await self.coordinator.async_request_refresh()
