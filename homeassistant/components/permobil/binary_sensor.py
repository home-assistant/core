"""Platform for binary sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mypermobil import BATTERY_CHARGING

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MyPermobilCoordinator
from .entity import PermobilEntity


@dataclass(frozen=True, kw_only=True)
class PermobilBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Permobil binary sensor entity."""

    is_on_fn: Callable[[Any], bool]
    available_fn: Callable[[Any], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[PermobilBinarySensorEntityDescription, ...] = (
    PermobilBinarySensorEntityDescription(
        is_on_fn=lambda data: data.battery[BATTERY_CHARGING[0]],
        available_fn=lambda data: BATTERY_CHARGING[0] in data.battery,
        key="is_charging",
        translation_key="is_charging",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create and setup the binary sensor."""

    coordinator: MyPermobilCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        PermobilbinarySensor(coordinator=coordinator, description=description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class PermobilbinarySensor(PermobilEntity, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    entity_description: PermobilBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return True if the wheelchair is charging."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return True if the sensor has value."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )
