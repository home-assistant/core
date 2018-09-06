"""
This component provides HA sensor support for Amcrest IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.amcrest/
"""
import asyncio
from datetime import timedelta
import logging

from homeassistant.components.amcrest import DATA_AMCREST, SENSORS
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, CONF_SENSORS, STATE_UNKNOWN

DEPENDENCIES = ['amcrest']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
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
    return True


class AmcrestSensor(Entity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(self, name, camera, sensor_type):
        """Initialize a sensor for Amcrest camera."""
        self._attrs = {}
        self._camera = camera
        self._sensor_type = sensor_type
        self._name = '{0}_{1}'.format(name,
                                      SENSORS.get(self._sensor_type)[0])
        self._icon = 'mdi:{}'.format(SENSORS.get(self._sensor_type)[2])
        self._state = STATE_UNKNOWN

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

        try:
            version, build_date = self._camera.software_information
            self._attrs['Build Date'] = build_date.split('=')[-1]
            self._attrs['Version'] = version.split('=')[-1]
        except ValueError:
            self._attrs['Build Date'] = 'Not Available'
            self._attrs['Version'] = 'Not Available'

        try:
            self._attrs['Serial Number'] = self._camera.serial_number
        except ValueError:
            self._attrs['Serial Number'] = 'Not Available'

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
