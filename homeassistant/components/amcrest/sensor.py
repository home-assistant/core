"""Suppoort for Amcrest IP camera sensors."""
from datetime import timedelta
import logging

from homeassistant.const import CONF_NAME, CONF_SENSORS
from homeassistant.helpers.entity import Entity

from .const import DATA_AMCREST, SENSOR_SCAN_INTERVAL_SECS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

# Sensor types are defined like: Name, units, icon
SENSOR_MOTION_DETECTOR = 'motion_detector'
SENSORS = {
    SENSOR_MOTION_DETECTOR: ['Motion Detected', None, 'mdi:run'],
    'sdcard': ['SD Used', '%', 'mdi:sd'],
    'ptz_preset': ['PTZ Preset', None, 'mdi:camera-iris'],
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up a sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST]['devices'][name]
    async_add_entities(
        [AmcrestSensor(name, device, sensor_type)
         for sensor_type in discovery_info[CONF_SENSORS]],
        True)


class AmcrestSensor(Entity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(self, name, device, sensor_type):
        """Initialize a sensor for Amcrest camera."""
        self._name = '{} {}'.format(name, SENSORS[sensor_type][0])
        self._api = device.api
        self._sensor_type = sensor_type
        self._state = None
        self._attrs = {}
        self._unit_of_measurement = SENSORS[sensor_type][1]
        self._icon = SENSORS[sensor_type][2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Pulling data from %s sensor.", self._name)

        if self._sensor_type == 'motion_detector':
            self._state = self._api.is_motion_detected
            self._attrs['Record Mode'] = self._api.record_mode

        elif self._sensor_type == 'ptz_preset':
            self._state = self._api.ptz_presets_count

        elif self._sensor_type == 'sdcard':
            storage = self._api.storage_all
            try:
                self._attrs['Total'] = '{:.2f} {}'.format(*storage['total'])
            except ValueError:
                self._attrs['Total'] = '{} {}'.format(*storage['total'])
            try:
                self._attrs['Used'] = '{:.2f} {}'.format(*storage['used'])
            except ValueError:
                self._attrs['Used'] = '{} {}'.format(*storage['used'])
            try:
                self._state = '{:.2f}'.format(storage['used_percent'])
            except ValueError:
                self._state = storage['used_percent']
