"""Support for Fumis switch entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fumis import Fumis, FumisInfo

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FumisConfigEntry, FumisDataUpdateCoordinator
from .entity import FumisEntity
from .helpers import fumis_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class FumisSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Fumis switch entity."""

    has_fn: Callable[[FumisInfo], bool] = lambda _: True
    is_on_fn: Callable[[FumisInfo], bool]
    turn_on_fn: Callable[[Fumis], Awaitable[Any]]
    turn_off_fn: Callable[[Fumis], Awaitable[Any]]


SWITCHES: tuple[FumisSwitchEntityDescription, ...] = (
    FumisSwitchEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        entity_category=EntityCategory.CONFIG,
        has_fn=lambda data: data.controller.eco_mode is not None,
        is_on_fn=lambda data: (
            data.controller.eco_mode.enabled if data.controller.eco_mode else False
        ),
        turn_on_fn=lambda client: client.set_eco_mode(enabled=True),
        turn_off_fn=lambda client: client.set_eco_mode(enabled=False),
    ),
    FumisSwitchEntityDescription(
        key="timer",
        translation_key="timer",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda data: data.controller.timer_enable,
        turn_on_fn=lambda client: client.set_timer(enabled=True),
        turn_off_fn=lambda client: client.set_timer(enabled=False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FumisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fumis switch entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        FumisSwitchEntity(coordinator=coordinator, description=description)
        for description in SWITCHES
        if description.has_fn(coordinator.data)
    )


class FumisSwitchEntity(FumisEntity, SwitchEntity):
    """Defines a Fumis switch entity."""

    entity_description: FumisSwitchEntityDescription

    def __init__(
        self,
        coordinator: FumisDataUpdateCoordinator,
        description: FumisSwitchEntityDescription,
    ) -> None:
        """Initialize the Fumis switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @fumis_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.turn_on_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()

    @fumis_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.turn_off_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()
