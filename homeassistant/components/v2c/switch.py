"""Switch platform for V2C EVSE."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from pytrydan import Trydan, TrydanData
from pytrydan.models.trydan import (
    ChargePointTimerState,
    DynamicState,
    LockState,
    PauseDynamicState,
    PauseState,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import V2CConfigEntry
from .coordinator import V2CUpdateCoordinator
from .entity import V2CBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class V2CSwitchEntityDescription(SwitchEntityDescription):
    """Describes a V2C EVSE switch entity."""

    value_fn: Callable[[TrydanData], bool]
    turn_on_fn: Callable[[Trydan], Coroutine[Any, Any, Any]]
    turn_off_fn: Callable[[Trydan], Coroutine[Any, Any, Any]]


TRYDAN_SWITCHES = (
    V2CSwitchEntityDescription(
        key="paused",
        translation_key="paused",
        value_fn=lambda evse_data: evse_data.paused == PauseState.PAUSED,
        turn_on_fn=lambda evse: evse.pause(),
        turn_off_fn=lambda evse: evse.resume(),
    ),
    V2CSwitchEntityDescription(
        key="locked",
        translation_key="locked",
        value_fn=lambda evse_data: evse_data.locked == LockState.ENABLED,
        turn_on_fn=lambda evse: evse.lock(),
        turn_off_fn=lambda evse: evse.unlock(),
    ),
    V2CSwitchEntityDescription(
        key="timer",
        translation_key="timer",
        value_fn=lambda evse_data: evse_data.timer == ChargePointTimerState.TIMER_ON,
        turn_on_fn=lambda evse: evse.timer(),
        turn_off_fn=lambda evse: evse.timer_disable(),
    ),
    V2CSwitchEntityDescription(
        key="dynamic",
        translation_key="dynamic",
        value_fn=lambda evse_data: evse_data.dynamic == DynamicState.ENABLED,
        turn_on_fn=lambda evse: evse.dynamic(),
        turn_off_fn=lambda evse: evse.dynamic_disable(),
    ),
    V2CSwitchEntityDescription(
        key="pause_dynamic",
        translation_key="pause_dynamic",
        icon="mdi:pause",
        value_fn=lambda evse_data: evse_data.pause_dynamic
        == PauseDynamicState.NOT_MODULATING,
        turn_on_fn=lambda evse: evse.pause_dynamic(),
        turn_off_fn=lambda evse: evse.resume_dynamic(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up V2C switch platform."""
    coordinator = config_entry.runtime_data

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the EVSE switch."""
        await self.entity_description.turn_on_fn(self.coordinator.evse)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the EVSE switch."""
        await self.entity_description.turn_off_fn(self.coordinator.evse)
        await self.coordinator.async_request_refresh()
