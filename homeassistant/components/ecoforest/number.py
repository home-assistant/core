"""Support for Ecoforest number platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription

from .const import DOMAIN
from .entity import EcoforestEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyecoforest.models.device import Device

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcoforestCoordinator


@dataclass(frozen=True, kw_only=True)
class EcoforestNumberEntityDescription(NumberEntityDescription):
    """Describes an ecoforest number entity."""

    value_fn: Callable[[Device], float | None]


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
