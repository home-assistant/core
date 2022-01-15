"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird import RainbirdController

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    DATA_RAINBIRD,
    RAINBIRD_CONTROLLER,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Rain Bird sensor."""

    if discovery_info is None:
        return

    controller = hass.data[DATA_RAINBIRD][discovery_info[RAINBIRD_CONTROLLER]]
    add_entities(
        [RainBirdSensor(controller, description) for description in SENSOR_TYPES],
        True,
    )


class RainBirdSensor(SensorEntity):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        controller: RainbirdController,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        self.entity_description = description
        self._controller = controller

    def update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor: %s", self.name)
        if self.entity_description.key == SENSOR_TYPE_RAINSENSOR:
            self._attr_native_value = self._controller.get_rain_sensor_state()
        elif self.entity_description.key == SENSOR_TYPE_RAINDELAY:
            self._attr_native_value = self._controller.get_rain_delay()
