"""Support for Ecoforest number platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyecoforest.models.device import Device

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EcoforestCoordinator
from .entity import EcoforestEntity


@dataclass(frozen=True)
class EcoforestRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Device], float | None]


@dataclass(frozen=True)
class EcoforestNumberEntityDescription(
    NumberEntityDescription, EcoforestRequiredKeysMixin
):
    """Describes an ecoforest number entity."""


NUMBER_ENTITIES = (
    EcoforestNumberEntityDescription(
        key="power_level",
        translation_key="power_level",
        native_min_value=1,
        native_max_value=9,
        native_step=1,
        value_fn=lambda data: data.power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ecoforest number platform."""
    coordinator: EcoforestCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        EcoforestNumberEntity(coordinator, description)
        for description in NUMBER_ENTITIES
    ]

    async_add_entities(entities)


class EcoforestNumberEntity(EcoforestEntity, NumberEntity):
    """Representation of an Ecoforest number entity."""

    entity_description: EcoforestNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self.data)

    async def async_set_native_value(self, value: float) -> None:
        """Update the native value."""
        await self.coordinator.api.set_power(int(value))
        await self.coordinator.async_request_refresh()
