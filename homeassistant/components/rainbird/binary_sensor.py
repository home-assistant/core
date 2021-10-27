"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

from pyrainbird import RainbirdController

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from . import (
    BINARY_SENSOR_TYPES,
    DATA_RAINBIRD,
    RAINBIRD_CONTROLLER,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Rain Bird sensor."""
    if discovery_info is None:
        return

    controller = hass.data[DATA_RAINBIRD][discovery_info[RAINBIRD_CONTROLLER]]
    add_entities(
        [
            RainBirdSensor(controller, description)
            for description in BINARY_SENSOR_TYPES
        ],
        True,
    )


class RainBirdSensor(BinarySensorEntity):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        controller: RainbirdController,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        self.entity_description = description
        self._controller = controller

    def update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor: %s", self.name)
        state = None
        if self.entity_description.key == SENSOR_TYPE_RAINSENSOR:
            state = self._controller.get_rain_sensor_state()
        elif self.entity_description.key == SENSOR_TYPE_RAINDELAY:
            state = self._controller.get_rain_delay()
        self._attr_is_on = None if state is None else bool(state)
