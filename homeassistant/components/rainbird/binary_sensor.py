"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import BINARY_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Rain Bird sensor."""
    if discovery_info is None:
        return

    async_add_entities(
        [
            RainBirdSensor(discovery_info[description.key], description)
            for description in BINARY_SENSOR_TYPES
        ],
        True,
    )


class RainBirdSensor(CoordinatorEntity, BinarySensorEntity):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return None if self.coordinator.data is None else bool(self.coordinator.data)
