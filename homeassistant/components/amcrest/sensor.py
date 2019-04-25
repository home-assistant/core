"""Suppoort for Amcrest IP camera sensors."""
from datetime import timedelta
import logging

from homeassistant.const import CONF_NAME, CONF_SENSORS
from homeassistant.helpers.entity import Entity

from . import DATA_AMCREST, SENSORS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up a sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    device_name = discovery_info[CONF_NAME]
    sensors = discovery_info[CONF_SENSORS]
    amcrest = hass.data[DATA_AMCREST][device_name]

    amcrest_sensors = []
    for sensor_type in sensors:
        amcrest_sensors.append(
            AmcrestSensor(amcrest.name, amcrest.device, sensor_type))

    async_add_entities(amcrest_sensors, True)


class AmcrestSensor(Entity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(self, name, camera, sensor_type):
        """Initialize a sensor for Amcrest camera."""
        self._attrs = {}
        self._camera = camera
        self._sensor_type = sensor_type
        self._name = '{0}_{1}'.format(
            name, SENSORS.get(self._sensor_type)[0])
        self._icon = 'mdi:{}'.format(SENSORS.get(self._sensor_type)[2])
        self._state = None

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
        return SENSORS.get(self._sensor_type)[1]

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Pulling data from %s sensor.", self._name)

        if self._sensor_type == 'motion_detector':
            self._state = self._camera.is_motion_detected
            self._attrs['Record Mode'] = self._camera.record_mode

        elif self._sensor_type == 'ptz_preset':
            self._state = self._camera.ptz_presets_count

        elif self._sensor_type == 'sdcard':
            sd_used = self._camera.storage_used
            sd_total = self._camera.storage_total
            self._attrs['Total'] = '{0} {1}'.format(*sd_total)
            self._attrs['Used'] = '{0} {1}'.format(*sd_used)
            self._state = self._camera.storage_used_percent
