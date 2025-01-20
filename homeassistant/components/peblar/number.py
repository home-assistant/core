"""Support for Peblar numbers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from peblar import PeblarApi

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import (
    PeblarConfigEntry,
    PeblarData,
    PeblarDataUpdateCoordinator,
    PeblarRuntimeData,
)
from .entity import PeblarEntity
from .helpers import peblar_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PeblarNumberEntityDescription(NumberEntityDescription):
    """Describe a Peblar number."""

    native_max_value_fn: Callable[[PeblarRuntimeData], int]
    set_value_fn: Callable[[PeblarApi, float], Awaitable[Any]]
    value_fn: Callable[[PeblarData], int | None]


DESCRIPTIONS = [
    PeblarNumberEntityDescription(
        key="charge_current_limit",
        translation_key="charge_current_limit",
        device_class=NumberDeviceClass.CURRENT,
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=6,
        native_max_value_fn=lambda x: x.user_configuration_coordinator.data.user_defined_charge_limit_current,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        set_value_fn=lambda x, v: x.ev_interface(charge_current_limit=int(v) * 1000),
        value_fn=lambda x: round(x.ev.charge_current_limit / 1000),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar number based on a config entry."""
    async_add_entities(
        PeblarNumberEntity(
            entry=entry,
            coordinator=entry.runtime_data.data_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarNumberEntity(
    PeblarEntity[PeblarDataUpdateCoordinator],
    NumberEntity,
):
    """Defines a Peblar number."""

    entity_description: PeblarNumberEntityDescription

    def __init__(
        self,
        entry: PeblarConfigEntry,
        coordinator: PeblarDataUpdateCoordinator,
        description: PeblarNumberEntityDescription,
    ) -> None:
        """Initialize the Peblar entity."""
        super().__init__(entry=entry, coordinator=coordinator, description=description)
        self._attr_native_max_value = description.native_max_value_fn(
            entry.runtime_data
        )

    @property
    def native_value(self) -> int | None:
        """Return the number value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @peblar_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        await self.entity_description.set_value_fn(self.coordinator.api, value)
        await self.coordinator.async_request_refresh()
