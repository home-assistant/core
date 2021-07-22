"""Support for Rain Bird Irrigation system LNK WiFi Module."""
import logging

from pyrainbird import RainbirdController

from homeassistant.components.sensor import SensorEntity

from . import (
    DATA_RAINBIRD,
    RAINBIRD_CONTROLLER,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
    SENSOR_TYPES,
    RainBirdSensorMetadata,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Rain Bird sensor."""

    if discovery_info is None:
        return

    controller = hass.data[DATA_RAINBIRD][discovery_info[RAINBIRD_CONTROLLER]]
    add_entities(
        [
            RainBirdSensor(controller, sensor_type, metadata)
            for sensor_type, metadata in SENSOR_TYPES.items()
        ],
        True,
    )


class RainBirdSensor(SensorEntity):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        controller: RainbirdController,
        sensor_type,
        metadata: RainBirdSensorMetadata,
    ):
        """Initialize the Rain Bird sensor."""
        self._sensor_type = sensor_type
        self._controller = controller

        self._attr_name = metadata.name
        self._attr_icon = metadata.icon
        self._attr_unit_of_measurement = metadata.unit_of_measurement
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor: %s", self.name)
        if self._sensor_type == SENSOR_TYPE_RAINSENSOR:
            self._state = self._controller.get_rain_sensor_state()
        elif self._sensor_type == SENSOR_TYPE_RAINDELAY:
            self._state = self._controller.get_rain_delay()
