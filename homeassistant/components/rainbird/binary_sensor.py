"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.rainbird import sensor
from homeassistant.components.rainbird.sensor import PARENT_SENSOR

from . import SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Rain Bird sensor."""
    if discovery_info is None or not PARENT_SENSOR in discovery_info:
        return False

    add_entities([RainBirdSensor(discovery_info[PARENT_SENSOR])], True)


class RainBirdSensor(BinarySensorDevice):
    """A sensor implementation for Rain Bird device."""

    def __init__(self, parent: sensor.RainbirdSensor):
        """Initialize the Rain Bird sensor."""
        self._parent = parent
        self._name = SENSOR_TYPES[parent._sensor_type][0]
        self._icon = SENSOR_TYPES[parent._sensor_type][2]
        self._state = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return None if self._parent.state is None else bool(self._parent.state)

    def update(self):
        """Get the latest data and updates the states."""
        self._parent.update()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return self._icon
