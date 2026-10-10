"""Support for Rituals Perfume Genie binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RitualsConfigEntry, RitualsData
from .entity import DiffuserEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RitualsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Rituals binary sensor entities."""

    is_on_fn: Callable[[RitualsData], bool | None]
    has_fn: Callable[[RitualsData], bool]


ENTITY_DESCRIPTIONS = (
    RitualsBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.sensors.battery_charging,
        has_fn=lambda data: data.hub.has_battery,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser binary sensors."""
    coordinators = config_entry.runtime_data

    async_add_entities(
        RitualsBinarySensorEntity(coordinator, description)
        for coordinator in coordinators.values()
        for description in ENTITY_DESCRIPTIONS
        if description.has_fn(coordinator.data)
    )


class RitualsBinarySensorEntity(DiffuserEntity, BinarySensorEntity):
    """Defines a Rituals binary sensor entity."""

    entity_description: RitualsBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)
