"""Support for Fumis number entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fumis import Fumis, FumisInfo

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FumisConfigEntry, FumisDataUpdateCoordinator
from .entity import FumisEntity
from .helpers import fumis_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class FumisNumberEntityDescription(NumberEntityDescription):
    """Describes a Fumis number entity."""

    has_fn: Callable[[FumisInfo], bool] = lambda _: True
    value_fn: Callable[[FumisInfo], float | None]
    set_fn: Callable[[Fumis, float], Awaitable[Any]]


NUMBERS: tuple[FumisNumberEntityDescription, ...] = (
    FumisNumberEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        has_fn=lambda data: len(data.controller.fans) > 0,
        value_fn=lambda data: (
            data.controller.fans[0].speed if data.controller.fans else None
        ),
        set_fn=lambda client, value: client.set_fan_speed(int(value)),
    ),
    FumisNumberEntityDescription(
        key="power_level",
        translation_key="power_level",
        native_min_value=1,
        native_max_value=5,
        native_step=1,
        value_fn=lambda data: data.controller.power.set_power,
        set_fn=lambda client, value: client.set_power(int(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FumisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fumis number entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        FumisNumberEntity(coordinator=coordinator, description=description)
        for description in NUMBERS
        if description.has_fn(coordinator.data)
    )


class FumisNumberEntity(FumisEntity, NumberEntity):
    """Defines a Fumis number entity."""

    entity_description: FumisNumberEntityDescription

    def __init__(
        self,
        coordinator: FumisDataUpdateCoordinator,
        description: FumisNumberEntityDescription,
    ) -> None:
        """Initialize the Fumis number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @fumis_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.entity_description.set_fn(self.coordinator.client, value)
        await self.coordinator.async_request_refresh()
