"""Support for TechnoVE switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from technove import Station as TechnoVEStation

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TechnoVEConfigEntry
from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator
from .entity import TechnoVEEntity
from .helpers import technove_exception_handler


async def _set_charging_enabled(
    coordinator: TechnoVEDataUpdateCoordinator, enabled: bool
) -> None:
    if coordinator.data.info.auto_charge:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="set_charging_enabled_on_auto_charge",
        )
    await coordinator.technove.set_charging_enabled(enabled=enabled)
    coordinator.data.info.is_session_active = enabled
    coordinator.async_set_updated_data(coordinator.data)


async def _enable_charging(coordinator: TechnoVEDataUpdateCoordinator) -> None:
    await _set_charging_enabled(coordinator, True)


async def _disable_charging(coordinator: TechnoVEDataUpdateCoordinator) -> None:
    await _set_charging_enabled(coordinator, False)


async def _set_auto_charge(
    coordinator: TechnoVEDataUpdateCoordinator, enabled: bool
) -> None:
    await coordinator.technove.set_auto_charge(enabled=enabled)


@dataclass(frozen=True, kw_only=True)
class TechnoVESwitchDescription(SwitchEntityDescription):
    """Describes TechnoVE binary sensor entity."""

    is_on_fn: Callable[[TechnoVEStation], bool]
    turn_on_fn: Callable[[TechnoVEDataUpdateCoordinator], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[TechnoVEDataUpdateCoordinator], Coroutine[Any, Any, None]]


SWITCHES = [
    TechnoVESwitchDescription(
        key="auto_charge",
        translation_key="auto_charge",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda station: station.info.auto_charge,
        turn_on_fn=lambda coordinator: _set_auto_charge(coordinator, True),
        turn_off_fn=lambda coordinator: _set_auto_charge(coordinator, False),
    ),
    TechnoVESwitchDescription(
        key="session_active",
        translation_key="session_active",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda station: station.info.is_session_active,
        turn_on_fn=_enable_charging,
        turn_off_fn=_disable_charging,
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
        await self.entity_description.turn_on_fn(self.coordinator)

    @technove_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the TechnoVE switch."""
        await self.entity_description.turn_off_fn(self.coordinator)
