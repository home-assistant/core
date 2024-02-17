"""Platform for binary sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from mypermobil import BATTERY_CHARGING

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyPermobilCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PermobilBinaryRequiredKeysMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[Any], bool]
    available_fn: Callable[[Any], bool]


@dataclass(frozen=True)
class PermobilBinarySensorEntityDescription(
    BinarySensorEntityDescription, PermobilBinaryRequiredKeysMixin
):
    """Describes Permobil binary sensor entity."""


BINARY_SENSOR_DESCRIPTIONS: tuple[PermobilBinarySensorEntityDescription, ...] = (
    PermobilBinarySensorEntityDescription(
        is_on_fn=lambda data: data.battery[BATTERY_CHARGING[0]],
        available_fn=lambda data: BATTERY_CHARGING[0] in data.battery,
        key="is_charging",
        translation_key="is_charging",
        icon="mdi:battery_unknown",
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


class PermobilbinarySensor(
    CoordinatorEntity[MyPermobilCoordinator], BinarySensorEntity
):
    """Representation of a Binary Sensor."""

    _attr_has_entity_name = True
    entity_description: PermobilBinarySensorEntityDescription
    _available = True

    def __init__(
        self,
        coordinator: MyPermobilCoordinator,
        description: PermobilBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.p_api.email}_{self.entity_description.key}"
        )

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
