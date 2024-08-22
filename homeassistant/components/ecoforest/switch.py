"""Switch platform for Ecoforest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .const import DOMAIN
from .entity import EcoforestEntity

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pyecoforest.api import EcoforestApi
    from pyecoforest.models.device import Device

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcoforestCoordinator


@dataclass(frozen=True, kw_only=True)
class EcoforestSwitchEntityDescription(SwitchEntityDescription):
    """Describes an Ecoforest switch entity."""

    value_fn: Callable[[Device], bool]
    switch_fn: Callable[[EcoforestApi, bool], Awaitable[Device]]


SWITCH_TYPES: tuple[EcoforestSwitchEntityDescription, ...] = (
    EcoforestSwitchEntityDescription(
        key="status",
        name=None,
        value_fn=lambda data: data.on,
        switch_fn=lambda api, status: api.turn(status),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ecoforest switch platform."""
    coordinator: EcoforestCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        EcoforestSwitchEntity(coordinator, description) for description in SWITCH_TYPES
    ]

    async_add_entities(entities)


class EcoforestSwitchEntity(EcoforestEntity, SwitchEntity):
    """Representation of an Ecoforest switch entity."""

    entity_description: EcoforestSwitchEntityDescription

    @property
    def is_on(self) -> bool:
        """Return the state of the ecoforest device."""
        return self.entity_description.value_fn(self.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the ecoforest device."""
        await self.entity_description.switch_fn(self.coordinator.api, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the ecoforest device."""
        await self.entity_description.switch_fn(self.coordinator.api, False)
        await self.coordinator.async_request_refresh()
