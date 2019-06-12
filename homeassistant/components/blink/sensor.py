"""Support for Blink system camera sensors."""
import logging

from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity

from . import BLINK_DATA, SENSORS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Blink sensor."""
    if discovery_info is None:
        return
    data = hass.data[BLINK_DATA]
    devs = []
    for camera in data.cameras:
        for sensor_type in discovery_info[CONF_MONITORED_CONDITIONS]:
            devs.append(BlinkSensor(data, camera, sensor_type))

    add_entities(devs, True)


class BlinkSensor(Entity):
    """A Blink camera sensor."""

    def __init__(self, data, camera, sensor_type):
        """Initialize sensors from Blink camera."""
        name, units, icon = SENSORS[sensor_type]
        self._name = "{} {} {}".format(
            BLINK_DATA, camera, name)
        self._camera_name = name
        self._type = sensor_type
        self.data = data
        self._camera = data.cameras[camera]
        self._state = None
        self._unit_of_measurement = units
        self._icon = icon
        self._unique_id = "{}-{}".format(self._camera.serial, self._type)
        self._sensor_key = self._type
        if self._type == 'temperature':
            self._sensor_key = 'temperature_calibrated'

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id for the camera sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the camera's current state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Retrieve sensor data from the camera."""
        self.data.refresh()
        try:
            self._state = self._camera.attributes[self._sensor_key]
        except KeyError:
            self._state = None
            _LOGGER.error(
                "%s not a valid camera attribute. Did the API change?",
                self._sensor_key)
