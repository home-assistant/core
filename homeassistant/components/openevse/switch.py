"""Support for OpenEVSE switch entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from openevsehttp import OpenEVSE

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenEVSEConfigEntry
from .entity import OpenEVSEEntity
from .helpers import openevse_exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenEVSESwitchDescription(SwitchEntityDescription):
    """Describes an OpenEVSE switch entity."""

    is_on_fn: Callable[[OpenEVSE], bool | None]
    turn_on_fn: Callable[[OpenEVSE], Awaitable[Any]]
    turn_off_fn: Callable[[OpenEVSE], Awaitable[Any]]


SWITCH_TYPES: tuple[OpenEVSESwitchDescription, ...] = (
    OpenEVSESwitchDescription(
        key="solar_pv_divert",
        translation_key="solar_pv_divert",
        is_on_fn=lambda ev: (
            ev.divertmode == "eco" if ev.divertmode is not None else None
        ),
        turn_on_fn=lambda ev: ev.set_divert_mode("eco"),
        turn_off_fn=lambda ev: ev.set_divert_mode(
            "fast"
        ),  # "fast" disables solar divert
    ),
    OpenEVSESwitchDescription(
        key="current_shaper",
        translation_key="current_shaper",
        is_on_fn=lambda ev: ev.shaper_active,
        turn_on_fn=lambda ev: ev.set_shaper(True),
        turn_off_fn=lambda ev: ev.set_shaper(False),
    ),
    OpenEVSESwitchDescription(
        key="manual_override",
        translation_key="manual_override",
        is_on_fn=lambda ev: ev.manual_override,
        turn_on_fn=lambda ev: ev.toggle_override(),
        turn_off_fn=lambda ev: ev.toggle_override(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE switches based on config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        OpenEVSESwitch(
            coordinator,
            description,
            entry.unique_id or entry.entry_id,
            entry.unique_id,
        )
        for description in SWITCH_TYPES
    )


class OpenEVSESwitch(OpenEVSEEntity, SwitchEntity):
    """Implementation of an OpenEVSE switch."""

    entity_description: OpenEVSESwitchDescription

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.is_on_fn(self.coordinator.charger) is not None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.entity_description.is_on_fn(self.coordinator.charger)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        with openevse_exception_handler():
            await self.entity_description.turn_on_fn(self.coordinator.charger)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        with openevse_exception_handler():
            await self.entity_description.turn_off_fn(self.coordinator.charger)
