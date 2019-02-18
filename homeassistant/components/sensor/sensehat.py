"""
Support for Sense HAT sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.sensehat
"""
import os
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (TEMP_CELSIUS, CONF_DISPLAY_OPTIONS, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['sense-hat==2.2.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'sensehat'
CONF_IS_HAT_ATTACHED = 'is_hat_attached'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_TYPES = {
    'temperature': ['temperature', TEMP_CELSIUS],
    'humidity': ['humidity', '%'],
    'pressure': ['pressure', 'mb'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DISPLAY_OPTIONS, default=list(SENSOR_TYPES)):
        [vol.In(SENSOR_TYPES)],
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_IS_HAT_ATTACHED, default=True): cv.boolean
})


def get_cpu_temp():
    """Get CPU temperature."""
    res = os.popen("vcgencmd measure_temp").readline()
    t_cpu = float(res.replace("temp=", "").replace("'C\n", ""))
    return t_cpu


def get_average(temp_base):
    """Use moving average to get better readings."""
    if not hasattr(get_average, "temp"):
        get_average.temp = [temp_base, temp_base, temp_base]
    get_average.temp[2] = get_average.temp[1]
    get_average.temp[1] = get_average.temp[0]
    get_average.temp[0] = temp_base
    temp_avg = (get_average.temp[0] + get_average.temp[1]
                + get_average.temp[2]) / 3
    return temp_avg


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sense HAT sensor platform."""
    data = SenseHatData(config.get(CONF_IS_HAT_ATTACHED))
    dev = []
    for variable in config[CONF_DISPLAY_OPTIONS]:
        dev.append(SenseHatSensor(data, variable))

    add_entities(dev, True)


class SenseHatSensor(Entity):
    """Representation of a Sense HAT sensor."""

    def __init__(self, data, sensor_types):
        """Initialize the sensor."""
        self.data = data
        self._name = SENSOR_TYPES[sensor_types][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_types][1]
        self.type = sensor_types
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
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        if not self.data.humidity:
            _LOGGER.error("Don't receive data")
            return

        if self.type == 'temperature':
            self._state = self.data.temperature
        if self.type == 'humidity':
            self._state = self.data.humidity
        if self.type == 'pressure':
            self._state = self.data.pressure


class SenseHatData:
    """Get the latest data and update."""

    def __init__(self, is_hat_attached):
        """Initialize the data object."""
        self.temperature = None
        self.humidity = None
        self.pressure = None
        self.is_hat_attached = is_hat_attached

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Sense HAT."""
        from sense_hat import SenseHat
        sense = SenseHat()
        temp_from_h = sense.get_temperature_from_humidity()
        temp_from_p = sense.get_temperature_from_pressure()
        t_total = (temp_from_h + temp_from_p) / 2

        if self.is_hat_attached:
            t_cpu = get_cpu_temp()
            t_correct = t_total - ((t_cpu - t_total) / 1.5)
            t_correct = get_average(t_correct)
        else:
            t_correct = get_average(t_total)

        self.temperature = t_correct
        self.humidity = sense.get_humidity()
        self.pressure = sense.get_pressure()
