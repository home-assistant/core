"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

from pyrainbird import RainbirdController

from homeassistant.components import binary_sensor
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

from . import (
    DOMAIN,
    RAINBIRD_CONTROLLER,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
    SENSOR_TYPES,
)

PARENT_SENSOR = "parent_sensor"

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Rain Bird sensor."""

    if discovery_info is None or not RAINBIRD_CONTROLLER in discovery_info:
        return False

    devices = []
    for sensor_type in SENSOR_TYPES:
        sensor = RainBirdSensor(
            discovery_info[RAINBIRD_CONTROLLER], sensor_type
        )
        devices += [sensor]

        discovery.load_platform(
            hass,
            binary_sensor.DOMAIN,
            DOMAIN,
            discovered={PARENT_SENSOR: sensor},
            hass_config=config,
        )

    add_entities(devices, True)


class RainBirdSensor(Entity):
    """A sensor implementation for Rain Bird device."""

    def __init__(self, controller: RainbirdController, sensor_type):
        """Initialize the Rain Bird sensor."""
        self._sensor_type = sensor_type
        self._controller = controller
        self._name = SENSOR_TYPES[self._sensor_type][0]
        self._icon = SENSOR_TYPES[self._sensor_type][2]
        self._unit_of_measurement = SENSOR_TYPES[self._sensor_type][1]
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        if self._sensor_type == SENSOR_TYPE_RAINSENSOR:
            self._state = self._controller.get_rain_sensor_state()
        elif self._sensor_type == SENSOR_TYPE_RAINDELAY:
            self._state = self._controller.get_rain_delay()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return icon."""
        return self._icon
