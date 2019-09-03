"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

from homeassistant.helpers.entity import Entity
from pyrainbird import RainbirdController
from . import DATA_RAINBIRD

_LOGGER = logging.getLogger(__name__)

# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {"rainsensor": ["Rainsensor", None, "mdi:water"]}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Rain Bird sensor."""
    controller = hass.data[DATA_RAINBIRD]

    sensors = []
    for sensor_type in SENSOR_TYPES.keys():
        sensors.append(RainBirdSensor(controller, sensor_type))

    add_entities(sensors, True)


class RainBirdSensor(Entity):
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
        self._state = self._controller.get_rain_sensor_state()
        return None if self._state is None else bool(self._state)

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        if self._sensor_type == "rainsensor":
            self._state = self._controller.get_rain_sensor_state()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return self._icon
