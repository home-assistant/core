"""Support for Ecoforest number platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyecoforest.models.device import Device

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EcoforestConfigEntry
from .entity import EcoforestEntity


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
    EcoforestNumberEntityDescription(
        key="setpoint_temperature",
        translation_key="setpoint_temperature",
        native_min_value=10,
        native_max_value=30,
        native_step=0.5,
        value_fn=lambda data: data.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcoforestConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ecoforest number platform."""
    coordinator = config_entry.runtime_data

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
        if self.entity_description.key == "power_level":
            await self.coordinator.api.set_power(int(value))
        elif self.entity_description.key == "setpoint_temperature":
            await self.coordinator.api.set_temperature(value)
        await self.coordinator.async_request_refresh()
