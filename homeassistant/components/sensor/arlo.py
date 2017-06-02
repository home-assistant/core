"""
This component provides HA sensor for Netgear Arlo IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.arlo/
"""
import asyncio
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.components.arlo import (
    CONF_ATTRIBUTION, DEFAULT_BRAND)

from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, STATE_UNKNOWN)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['arlo']

_LOGGER = logging.getLogger(__name__)

# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    'last_capture': ['Last', None, 'run-fast'],
    'total_cameras': ['Arlo Cameras', None, 'video'],
    'captured_today': ['Captured Today', None, 'file-video'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

SCAN_INTERVAL = timedelta(seconds=90)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up an Arlo IP sensor."""
    arlo = hass.data.get('arlo')
    if not arlo:
        return False

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == 'total_cameras':
            sensors.append(ArloSensor(hass,
                                      SENSOR_TYPES[sensor_type][0],
                                      arlo,
                                      sensor_type))
        else:
            for camera in arlo.cameras:
                name = '{0} {1}'.format(SENSOR_TYPES[sensor_type][0],
                                        camera.name)
                sensors.append(ArloSensor(hass, name, camera, sensor_type))

    async_add_devices(sensors, True)
    return True


class ArloSensor(Entity):
    """An implementation of a Netgear Arlo IP sensor."""

    def __init__(self, hass, name, device, sensor_type):
        """Initialize an Arlo sensor."""
        super().__init__()
        self._name = name
        self._hass = hass
        self._data = device
        self._sensor_type = sensor_type
        self._state = None
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[2])

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[1]

    def update(self):
        """Get the latest data and updates the state."""
        self._data.update()

        if self._sensor_type == 'total_cameras':
            self._state = len(self._data.cameras)

        elif self._sensor_type == 'captured_today':
            self._state = len(self._data.captured_today)

        elif self._sensor_type == 'last_capture':
            try:
                video = self._data.videos()[0]
                self._state = video.created_at_pretty("%m-%d-%Y %H:%M:%S")
            except (AttributeError, IndexError):
                self._state = STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['brand'] = DEFAULT_BRAND

        if self._sensor_type == 'last_capture' or \
           self._sensor_type == 'captured_today':
            attrs['model'] = self._data.model_id

        return attrs
