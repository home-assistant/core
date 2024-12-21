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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    PeblarConfigEntry,
    PeblarData,
    PeblarDataUpdateCoordinator,
    PeblarRuntimeData,
)


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
        native_max_value_fn=lambda x: x.system_information.hardware_max_current,
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
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarNumberEntity(CoordinatorEntity[PeblarDataUpdateCoordinator], NumberEntity):
    """Defines a Peblar number."""

    entity_description: PeblarNumberEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PeblarConfigEntry,
        description: PeblarNumberEntityDescription,
    ) -> None:
        """Initialize the Peblar entity."""
        super().__init__(entry.runtime_data.data_coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, entry.runtime_data.system_information.product_serial_number)
            },
        )
        self._attr_native_max_value = description.native_max_value_fn(
            entry.runtime_data
        )

    @property
    def native_value(self) -> int | None:
        """Return the number value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        await self.entity_description.set_value_fn(self.coordinator.api, value)
        await self.coordinator.async_request_refresh()
