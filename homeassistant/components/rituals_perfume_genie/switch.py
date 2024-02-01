"""Support for Rituals Perfume Genie switches."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pyrituals import Diffuser

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity


@dataclass(frozen=True)
class RitualsEntityDescriptionMixin:
    """Mixin values for Rituals entities."""

    is_on_fn: Callable[[Diffuser], bool]
    turn_on_fn: Callable[[Diffuser], Awaitable[None]]
    turn_off_fn: Callable[[Diffuser], Awaitable[None]]


@dataclass(frozen=True)
class RitualsSwitchEntityDescription(
    SwitchEntityDescription, RitualsEntityDescriptionMixin
):
    """Class describing Rituals switch entities."""


ENTITY_DESCRIPTIONS = (
    RitualsSwitchEntityDescription(
        key="is_on",
        name=None,
        icon="mdi:fan",
        is_on_fn=lambda diffuser: diffuser.is_on,
        turn_on_fn=lambda diffuser: diffuser.turn_on(),
        turn_off_fn=lambda diffuser: diffuser.turn_off(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser switch."""
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        RitualsSwitchEntity(coordinator, description)
        for coordinator in coordinators.values()
        for description in ENTITY_DESCRIPTIONS
    )


class RitualsSwitchEntity(DiffuserEntity, SwitchEntity):
    """Representation of a diffuser switch."""

    entity_description: RitualsSwitchEntityDescription

    def __init__(
        self,
        coordinator: RitualsDataUpdateCoordinator,
        description: RitualsSwitchEntityDescription,
    ) -> None:
        """Initialize the diffuser switch."""
        super().__init__(coordinator, description)
        self._attr_is_on = description.is_on_fn(coordinator.diffuser)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on_fn(self.coordinator.diffuser)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off_fn(self.coordinator.diffuser)
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.entity_description.is_on_fn(self.coordinator.diffuser)
        super()._handle_coordinator_update()
