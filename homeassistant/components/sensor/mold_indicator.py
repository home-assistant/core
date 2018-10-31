"""
Calculates mold growth indication from temperature and humidity.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mold_indicator/
"""
import logging
import math

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant import util
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_state_change
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, TEMP_FAHRENHEIT, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_CRITICAL_TEMP = 'estimated_critical_temp'
ATTR_DEWPOINT = 'dewpoint'

CONF_CALIBRATION_FACTOR = 'calibration_factor'
CONF_INDOOR_HUMIDITY = 'indoor_humidity_sensor'
CONF_INDOOR_TEMP = 'indoor_temp_sensor'
CONF_OUTDOOR_TEMP = 'outdoor_temp_sensor'

DEFAULT_NAME = 'Mold Indicator'

MAGNUS_K2 = 17.62
MAGNUS_K3 = 243.12

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_INDOOR_TEMP): cv.entity_id,
    vol.Required(CONF_OUTDOOR_TEMP): cv.entity_id,
    vol.Required(CONF_INDOOR_HUMIDITY): cv.entity_id,
    vol.Optional(CONF_CALIBRATION_FACTOR): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up MoldIndicator sensor."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    indoor_temp_sensor = config.get(CONF_INDOOR_TEMP)
    outdoor_temp_sensor = config.get(CONF_OUTDOOR_TEMP)
    indoor_humidity_sensor = config.get(CONF_INDOOR_HUMIDITY)
    calib_factor = config.get(CONF_CALIBRATION_FACTOR)

    add_entities([MoldIndicator(
        hass, name, indoor_temp_sensor, outdoor_temp_sensor,
        indoor_humidity_sensor, calib_factor)], True)


class MoldIndicator(Entity):
    """Represents a MoldIndication sensor."""

    def __init__(self, hass, name, indoor_temp_sensor, outdoor_temp_sensor,
                 indoor_humidity_sensor, calib_factor):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._indoor_temp_sensor = indoor_temp_sensor
        self._indoor_humidity_sensor = indoor_humidity_sensor
        self._outdoor_temp_sensor = outdoor_temp_sensor
        self._calib_factor = calib_factor
        self._is_metric = hass.config.units.is_metric

        self._dewpoint = None
        self._indoor_temp = None
        self._outdoor_temp = None
        self._indoor_hum = None
        self._crit_temp = None

        track_state_change(hass, indoor_temp_sensor, self._sensor_changed)
        track_state_change(hass, outdoor_temp_sensor, self._sensor_changed)
        track_state_change(hass, indoor_humidity_sensor, self._sensor_changed)

        # Read initial state
        indoor_temp = hass.states.get(indoor_temp_sensor)
        outdoor_temp = hass.states.get(outdoor_temp_sensor)
        indoor_hum = hass.states.get(indoor_humidity_sensor)

        if indoor_temp:
            self._indoor_temp = MoldIndicator._update_temp_sensor(indoor_temp)

        if outdoor_temp:
            self._outdoor_temp = MoldIndicator._update_temp_sensor(
                outdoor_temp)

        if indoor_hum:
            self._indoor_hum = MoldIndicator._update_hum_sensor(indoor_hum)

    @staticmethod
    def _update_temp_sensor(state):
        """Parse temperature sensor value."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        temp = util.convert(state.state, float)

        if temp is None:
            _LOGGER.error('Unable to parse sensor temperature: %s',
                          state.state)
            return None

        # convert to celsius if necessary
        if unit == TEMP_FAHRENHEIT:
            return util.temperature.fahrenheit_to_celsius(temp)
        if unit == TEMP_CELSIUS:
            return temp
        _LOGGER.error("Temp sensor has unsupported unit: %s (allowed: %s, "
                      "%s)", unit, TEMP_CELSIUS, TEMP_FAHRENHEIT)

        return None

    @staticmethod
    def _update_hum_sensor(state):
        """Parse humidity sensor value."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        hum = util.convert(state.state, float)

        if hum is None:
            _LOGGER.error('Unable to parse sensor humidity: %s',
                          state.state)
            return None

        if unit != '%':
            _LOGGER.error("Humidity sensor has unsupported unit: %s %s",
                          unit, " (allowed: %)")

        if hum > 100 or hum < 0:
            _LOGGER.error("Humidity sensor out of range: %s %s", hum,
                          " (allowed: 0-100%)")

        return hum

    def update(self):
        """Calculate latest state."""
        # check all sensors
        if None in (self._indoor_temp, self._indoor_hum, self._outdoor_temp):
            return

        # re-calculate dewpoint and mold indicator
        self._calc_dewpoint()
        self._calc_moldindicator()

    def _sensor_changed(self, entity_id, old_state, new_state):
        """Handle sensor state changes."""
        if new_state is None:
            return

        if entity_id == self._indoor_temp_sensor:
            self._indoor_temp = MoldIndicator._update_temp_sensor(new_state)
        elif entity_id == self._outdoor_temp_sensor:
            self._outdoor_temp = MoldIndicator._update_temp_sensor(new_state)
        elif entity_id == self._indoor_humidity_sensor:
            self._indoor_hum = MoldIndicator._update_hum_sensor(new_state)

        self.update()
        self.schedule_update_ha_state()

    def _calc_dewpoint(self):
        """Calculate the dewpoint for the indoor air."""
        # Use magnus approximation to calculate the dew point
        alpha = MAGNUS_K2 * self._indoor_temp / (MAGNUS_K3 + self._indoor_temp)
        beta = MAGNUS_K2 * MAGNUS_K3 / (MAGNUS_K3 + self._indoor_temp)

        if self._indoor_hum == 0:
            self._dewpoint = -50  # not defined, assume very low value
        else:
            self._dewpoint = \
                MAGNUS_K3 * (alpha + math.log(self._indoor_hum / 100.0)) / \
                (beta - math.log(self._indoor_hum / 100.0))
        _LOGGER.debug("Dewpoint: %f %s", self._dewpoint, TEMP_CELSIUS)

    def _calc_moldindicator(self):
        """Calculate the humidity at the (cold) calibration point."""
        if None in (self._dewpoint, self._calib_factor) or \
           self._calib_factor == 0:

            _LOGGER.debug("Invalid inputs - dewpoint: %s,"
                          " calibration-factor: %s",
                          self._dewpoint, self._calib_factor)
            self._state = None
            return

        # first calculate the approximate temperature at the calibration point
        self._crit_temp = \
            self._outdoor_temp + (self._indoor_temp - self._outdoor_temp) / \
            self._calib_factor

        _LOGGER.debug("Estimated Critical Temperature: %f %s",
                      self._crit_temp, TEMP_CELSIUS)

        # Then calculate the humidity at this point
        alpha = MAGNUS_K2 * self._crit_temp / (MAGNUS_K3 + self._crit_temp)
        beta = MAGNUS_K2 * MAGNUS_K3 / (MAGNUS_K3 + self._crit_temp)

        crit_humidity = \
            math.exp(
                (self._dewpoint * beta - MAGNUS_K3 * alpha) /
                (self._dewpoint + MAGNUS_K3)) * 100.0

        # check bounds and format
        if crit_humidity > 100:
            self._state = '100'
        elif crit_humidity < 0:
            self._state = '0'
        else:
            self._state = '{0:d}'.format(int(crit_humidity))

        _LOGGER.debug("Mold indicator humidity: %s", self._state)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return '%'

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._is_metric:
            return {
                ATTR_DEWPOINT: self._dewpoint,
                ATTR_CRITICAL_TEMP: self._crit_temp,
            }
        return {
            ATTR_DEWPOINT:
                util.temperature.celsius_to_fahrenheit(self._dewpoint),
            ATTR_CRITICAL_TEMP:
                util.temperature.celsius_to_fahrenheit(self._crit_temp),
        }
