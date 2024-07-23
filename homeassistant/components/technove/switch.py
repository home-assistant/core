"""Support for TechnoVE switches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from technove import Station as TechnoVEStation, TechnoVE

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TechnoVEConfigEntry
from .coordinator import TechnoVEDataUpdateCoordinator
from .entity import TechnoVEEntity
from .helpers import technove_exception_handler


@dataclass(frozen=True, kw_only=True)
class TechnoVESwitchDescription(SwitchEntityDescription):
    """Describes TechnoVE binary sensor entity."""

    is_on_fn: Callable[[TechnoVEStation], bool]
    turn_on_fn: Callable[[TechnoVE], Awaitable[dict[str, Any]]]
    turn_off_fn: Callable[[TechnoVE], Awaitable[dict[str, Any]]]


SWITCHES = [
    TechnoVESwitchDescription(
        key="auto_charge",
        translation_key="auto_charge",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda station: station.info.auto_charge,
        turn_on_fn=lambda technoVE: technoVE.set_auto_charge(enabled=True),
        turn_off_fn=lambda technoVE: technoVE.set_auto_charge(enabled=False),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TechnoVEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TechnoVE switch based on a config entry."""

    async_add_entities(
        TechnoVESwitchEntity(entry.runtime_data, description)
        for description in SWITCHES
    )


class TechnoVESwitchEntity(TechnoVEEntity, SwitchEntity):
    """Defines a TechnoVE switch entity."""

    entity_description: TechnoVESwitchDescription

    def __init__(
        self,
        coordinator: TechnoVEDataUpdateCoordinator,
        description: TechnoVESwitchDescription,
    ) -> None:
        """Initialize a TechnoVE switch entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def is_on(self) -> bool:
        """Return the state of the TechnoVE switch."""

        return self.entity_description.is_on_fn(self.coordinator.data)

    @technove_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the TechnoVE switch."""
        await self.entity_description.turn_on_fn(self.coordinator.technove)
        await self.coordinator.async_request_refresh()

    @technove_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the TechnoVE switch."""
        await self.entity_description.turn_off_fn(self.coordinator.technove)
        await self.coordinator.async_request_refresh()
