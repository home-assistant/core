"""Support for OpenEVSE number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from openevsehttp import OpenEVSE

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenEVSEConfigEntry
from .entity import OpenEVSEEntity
from .helpers import openevse_exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenEVSENumberDescription(NumberEntityDescription):
    """Describes an OpenEVSE number entity."""

    value_fn: Callable[[OpenEVSE], float]
    min_value_fn: Callable[[OpenEVSE], float]
    max_value_fn: Callable[[OpenEVSE], float]
    set_value_fn: Callable[[OpenEVSE, float], Awaitable[Any]]


NUMBER_TYPES: tuple[OpenEVSENumberDescription, ...] = (
    OpenEVSENumberDescription(
        key="charge_rate",
        translation_key="charge_rate",
        value_fn=lambda ev: ev.max_current_soft or 0,
        min_value_fn=lambda ev: ev.min_amps or 0,
        max_value_fn=lambda ev: ev.max_amps or 0,
        set_value_fn=lambda ev, value: ev.set_current(int(value)),
        native_step=1.0,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE sensors based on config entry."""
    coordinator = entry.runtime_data
    identifier = entry.unique_id or entry.entry_id
    async_add_entities(
        OpenEVSENumber(coordinator, description, identifier, entry.unique_id)
        for description in NUMBER_TYPES
    )


class OpenEVSENumber(OpenEVSEEntity, NumberEntity):
    """Implementation of an OpenEVSE sensor."""

    entity_description: OpenEVSENumberDescription

    @property
    @override
    def native_value(self) -> float:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.coordinator.charger)

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.entity_description.min_value_fn(self.coordinator.charger)

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.entity_description.max_value_fn(self.coordinator.charger)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        with openevse_exception_handler(value):
            await self.entity_description.set_value_fn(self.coordinator.charger, value)
