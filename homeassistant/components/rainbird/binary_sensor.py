"""Support for Rain Bird Irrigation system LNK WiFi Module."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


RAIN_SENSOR_ENTITY_DESCRIPTION = BinarySensorEntityDescription(
    key="rainsensor",
    translation_key="rainsensor",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird binary_sensor."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator
    async_add_entities([RainBirdSensor(coordinator, RAIN_SENSOR_ENTITY_DESCRIPTION)])


class RainBirdSensor(CoordinatorEntity[RainbirdUpdateCoordinator], BinarySensorEntity):
    """A sensor implementation for Rain Bird device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.unique_id is not None:
            self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
            self._attr_device_info = coordinator.device_info
        else:
            self._attr_name = f"{coordinator.device_name} Rainsensor"

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.coordinator.data.rain
