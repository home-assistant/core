"""
This component provides HA sensor for Netgear Arlo IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.arlo/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.components.arlo import (
    CONF_ATTRIBUTION, DEFAULT_BRAND, DATA_ARLO, SIGNAL_UPDATE_ARLO)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY)

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['arlo']

# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    'last_capture': ['Last', None, 'run-fast'],
    'total_cameras': ['Arlo Cameras', None, 'video'],
    'captured_today': ['Captured Today', None, 'file-video'],
    'battery_level': ['Battery Level', '%', 'battery-50'],
    'signal_strength': ['Signal Strength', None, 'signal'],
    'temperature': ['Temperature', TEMP_CELSIUS, 'thermometer'],
    'humidity': ['Humidity', '%', 'water-percent'],
    'air_quality': ['Air Quality', 'ppm', 'biohazard']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an Arlo IP sensor."""
    arlo = hass.data.get(DATA_ARLO)
    if not arlo:
        return

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == 'total_cameras':
            sensors.append(ArloSensor(
                SENSOR_TYPES[sensor_type][0], arlo, sensor_type))
        else:
            for camera in arlo.cameras:
                if sensor_type in ('temperature', 'humidity', 'air_quality'):
                    continue

                name = '{0} {1}'.format(
                    SENSOR_TYPES[sensor_type][0], camera.name)
                sensors.append(ArloSensor(name, camera, sensor_type))

            for base_station in arlo.base_stations:
                if sensor_type in ('temperature', 'humidity', 'air_quality') \
                        and base_station.model_id == 'ABC1000':
                    name = '{0} {1}'.format(
                        SENSOR_TYPES[sensor_type][0], base_station.name)
                    sensors.append(ArloSensor(name, base_station, sensor_type))

    add_devices(sensors, True)


class ArloSensor(Entity):
    """An implementation of a Netgear Arlo IP sensor."""

    def __init__(self, name, device, sensor_type):
        """Initialize an Arlo sensor."""
        _LOGGER.debug('ArloSensor created for %s', name)
        self._name = name
        self._data = device
        self._sensor_type = sensor_type
        self._state = None
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[2])

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ARLO, self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == 'battery_level' and self._state is not None:
            return icon_for_battery_level(battery_level=int(self._state),
                                          charging=False)
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[1]

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._sensor_type == 'temperature':
            return DEVICE_CLASS_TEMPERATURE
        if self._sensor_type == 'humidity':
            return DEVICE_CLASS_HUMIDITY
        return None

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating Arlo sensor %s", self.name)
        if self._sensor_type == 'total_cameras':
            self._state = len(self._data.cameras)

        elif self._sensor_type == 'captured_today':
            self._state = len(self._data.captured_today)

        elif self._sensor_type == 'last_capture':
            try:
                video = self._data.last_video
                self._state = video.created_at_pretty("%m-%d-%Y %H:%M:%S")
            except (AttributeError, IndexError):
                error_msg = \
                    'Video not found for {0}. Older than {1} days?'.format(
                        self.name, self._data.min_days_vdo_cache)
                _LOGGER.debug(error_msg)
                self._state = None

        elif self._sensor_type == 'battery_level':
            try:
                self._state = self._data.battery_level
            except TypeError:
                self._state = None

        elif self._sensor_type == 'signal_strength':
            try:
                self._state = self._data.signal_strength
            except TypeError:
                self._state = None

        elif self._sensor_type == 'temperature':
            try:
                self._state = self._data.ambient_temperature
            except TypeError:
                self._state = None

        elif self._sensor_type == 'humidity':
            try:
                self._state = self._data.ambient_humidity
            except TypeError:
                self._state = None

        elif self._sensor_type == 'air_quality':
            try:
                self._state = self._data.ambient_air_quality
            except TypeError:
                self._state = None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['brand'] = DEFAULT_BRAND

        if self._sensor_type != 'total_cameras':
            attrs['model'] = self._data.model_id

        return attrs
