"""Switch platform for V2C EVSE."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from pytrydan import Trydan, TrydanData
from pytrydan.models.trydan import PauseState

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import V2CUpdateCoordinator
from .entity import V2CBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class V2CRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[TrydanData], bool]
    turn_on_fn: Callable[[Trydan], Coroutine[Any, Any, Any]]
    turn_off_fn: Callable[[Trydan], Coroutine[Any, Any, Any]]


@dataclass
class V2CSwitchEntityDescription(SwitchEntityDescription, V2CRequiredKeysMixin):
    """Describes a V2C EVSE switch entity."""


TRYDAN_SWITCHES = (
    V2CSwitchEntityDescription(
        key="paused",
        translation_key="paused",
        icon="mdi:pause",
        value_fn=lambda evse_data: evse_data.paused == PauseState.PAUSED,
        turn_on_fn=lambda evse: evse.pause(),
        turn_off_fn=lambda evse: evse.resume(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up V2C switch platform."""
    coordinator: V2CUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        V2CSwitchEntity(coordinator, description, config_entry.entry_id)
        for description in TRYDAN_SWITCHES
    )


class V2CSwitchEntity(V2CBaseEntity, SwitchEntity):
    """Representation of a V2C switch entity."""

    entity_description: V2CSwitchEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: SwitchEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C switch entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the EVSE switch."""
        return self.entity_description.value_fn(self.data)

    async def async_turn_on(self):
        """Turn on the EVSE switch."""
        await self.entity_description.turn_on_fn(self.coordinator.evse)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Turn off the EVSE switch."""
        await self.entity_description.turn_off_fn(self.coordinator.evse)
        await self.coordinator.async_request_refresh()
