"""
Support the sensor of a BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.bloomsky/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (TEMP_FAHRENHEIT, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['bloomsky']

# These are the available sensors
SENSOR_TYPES = ['Temperature',
                'Humidity',
                'Pressure',
                'Luminance',
                'UVIndex',
                'Voltage']

# Sensor units - these do not currently align with the API documentation
SENSOR_UNITS = {'Temperature': TEMP_FAHRENHEIT,
                'Humidity': '%',
                'Pressure': 'inHg',
                'Luminance': 'cd/m²',
                'Voltage': 'mV'}

# Which sensors to format numerically
FORMAT_NUMBERS = ['Temperature', 'Pressure', 'Voltage']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_TYPES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the available BloomSky weather sensors."""
    bloomsky = hass.components.bloomsky
    # Default needed in case of discovery
    sensors = config.get(CONF_MONITORED_CONDITIONS, SENSOR_TYPES)

    for device in bloomsky.BLOOMSKY.devices.values():
        for variable in sensors:
            add_devices(
                [BloomSkySensor(bloomsky.BLOOMSKY, device, variable)], True)


class BloomSkySensor(Entity):
    """Representation of a single sensor in a BloomSky device."""

    def __init__(self, bs, device, sensor_name):
        """Initialize a BloomSky sensor."""
        self._bloomsky = bs
        self._device_id = device['DeviceID']
        self._sensor_name = sensor_name
        self._name = '{} {}'.format(device['DeviceName'], sensor_name)
        self._state = None

    @property
    def name(self):
        """Return the name of the BloomSky device and this sensor."""
        return self._name

    @property
    def state(self):
        """Return the current state, eg. value, of this sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the sensor units."""
        return SENSOR_UNITS.get(self._sensor_name, None)

    def update(self):
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()

        state = \
            self._bloomsky.devices[self._device_id]['Data'][self._sensor_name]

        if self._sensor_name in FORMAT_NUMBERS:
            self._state = '{0:.2f}'.format(state)
        else:
            self._state = state
