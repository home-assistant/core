"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

from pyrainbird import RainbirdController

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import (
    DATA_RAINBIRD,
    RAINBIRD_CONTROLLER,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Rain Bird sensor."""
    if discovery_info is None:
        return

    controller = hass.data[DATA_RAINBIRD][discovery_info[RAINBIRD_CONTROLLER]]
    add_entities(
        [RainBirdSensor(controller, sensor_type) for sensor_type in SENSOR_TYPES], True
    )


class RainBirdSensor(BinarySensorEntity):
    """A sensor implementation for Rain Bird device."""

    def __init__(self, controller: RainbirdController, sensor_type):
        """Initialize the Rain Bird sensor."""
        self._sensor_type = sensor_type
        self._controller = controller
        self._name = SENSOR_TYPES[self._sensor_type][0]
        self._icon = SENSOR_TYPES[self._sensor_type][2]
        self._state = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return None if self._state is None else bool(self._state)

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        state = None
        if self._sensor_type == SENSOR_TYPE_RAINSENSOR:
            state = self._controller.get_rain_sensor_state()
        elif self._sensor_type == SENSOR_TYPE_RAINDELAY:
            state = self._controller.get_rain_delay()
        self._state = None if state is None else bool(state)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return self._icon
