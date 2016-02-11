"""
homeassistant.components.sensor.mold_indicator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Calculates mold growth indication from temperature and humidity

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mold_indicator/
"""
import logging
import math

import homeassistant.util as util
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_state_change
from homeassistant.const import (ATTR_UNIT_OF_MEASUREMENT,
                                 TEMP_CELCIUS, TEMP_FAHRENHEIT)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Mold Indicator"
CONF_INDOOR_TEMP = "indoor_temp_sensor"
CONF_OUTDOOR_TEMP = "outdoor_temp_sensor"
CONF_INDOOR_HUMIDITY = "indoor_humidity_sensor"
CONF_CALIBRATION_FACTOR = "calibration_factor"

MAGNUS_K2 = 17.62
MAGNUS_K3 = 243.12

ATTR_DEWPOINT = "Dewpoint"
ATTR_CRITICAL_TEMP = "Estimated Critical Temperature"


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Setup MoldIndicator sensor. """

    name = config.get('name', DEFAULT_NAME)
    indoor_temp_sensor = config.get(CONF_INDOOR_TEMP)
    outdoor_temp_sensor = config.get(CONF_OUTDOOR_TEMP)
    indoor_humidity_sensor = config.get(CONF_INDOOR_HUMIDITY)
    calib_value = util.convert(config.get(CONF_CALIBRATION_FACTOR),
                               float, None)

    if None in (indoor_temp_sensor,
                outdoor_temp_sensor, indoor_humidity_sensor):
        _LOGGER.error('Missing required key %s, %s or %s',
                      CONF_INDOOR_TEMP, CONF_OUTDOOR_TEMP,
                      CONF_INDOOR_HUMIDITY)
        return False

    add_devices_callback([MoldIndicator(
        hass, name, indoor_temp_sensor,
        outdoor_temp_sensor, indoor_humidity_sensor,
        calib_value)])


class MoldIndicator(Entity):
    """ Represents a MoldIndication sensor """

    def __init__(self, hass, name, indoor_temp_sensor, outdoor_temp_sensor,
                 indoor_humidity_sensor, calib_value):
        self._state = "-"
        self._hass = hass
        self._name = name
        self._indoor_temp_sensor = indoor_temp_sensor
        self._indoor_humidity_sensor = indoor_humidity_sensor
        self._outdoor_temp_sensor = outdoor_temp_sensor
        self._calib_value = calib_value
        self._is_metric = (hass.config.temperature_unit == TEMP_CELCIUS)

        self._dewpoint = None
        self._indoor_temp = None
        self._outdoor_temp = None
        self._indoor_hum = None
        self._crit_temp = None

        track_state_change(hass, indoor_temp_sensor, self._sensor_changed)
        track_state_change(hass, outdoor_temp_sensor, self._sensor_changed)
        track_state_change(hass, indoor_humidity_sensor, self._sensor_changed)

        # Read initial state
        self._sensor_changed(indoor_temp_sensor,
                             None, hass.states.get(indoor_temp_sensor))
        self._sensor_changed(outdoor_temp_sensor,
                             None, hass.states.get(outdoor_temp_sensor))
        self._sensor_changed(indoor_humidity_sensor,
                             None, hass.states.get(indoor_humidity_sensor))

    def _update_temp_sensor(self, state):
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        temp = util.convert(state.state, float)

        if temp is None:
            _LOGGER.error('Unable to parse sensor temperature: %s',
                          state.state)
            return None

        # convert to celsius if necessary
        if unit == TEMP_FAHRENHEIT:
            return util.temperature.fahrenheit_to_celcius(temp)
        elif unit == TEMP_CELCIUS:
            return temp
        else:
            _LOGGER.error("Temp sensor has unsupported unit: %s"
                          " (allowed: %s, %s)",
                          unit, TEMP_CELCIUS, TEMP_FAHRENHEIT)

        return None

    def _update_hum_sensor(self, state):
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        hum = util.convert(state.state, float)

        if hum is None:
            _LOGGER.error('Unable to parse sensor humidity: %s',
                          state.state)
            return None

        # check unit
        if unit != "%":
            _LOGGER.error(
                "Humidity sensor has unsupported unit: %s %s",
                unit,
                " (allowed: %)")

        # check range
        if hum > 100 or hum < 0:
            _LOGGER.error(
                "Humidity sensor out of range: %s %s",
                hum,
                " (allowed: 0-100%)")

        return hum

    def _sensor_changed(self, entity_id, old_state, new_state):
        """ Called when sensor values change """

        if new_state is None:
            return

        if entity_id == self._indoor_temp_sensor:
            # update the indoor temp sensor
            self._indoor_temp = self._update_temp_sensor(new_state)

        elif entity_id == self._outdoor_temp_sensor:
            # update outdoor temp sensor
            self._outdoor_temp = self._update_temp_sensor(new_state)

        elif entity_id == self._indoor_humidity_sensor:
            # update humidity
            self._indoor_hum = self._update_hum_sensor(new_state)

        # check all sensors
        if None in (self._indoor_temp, self._indoor_hum, self._outdoor_temp):
            return

        # re-calculate dewpoint and mold indicator
        self._calc_dewpoint()
        self._calc_moldindicator()
        self.update_ha_state()

    def _calc_dewpoint(self):
        """ Calculates the dewpoint for the indoor air """

        # use magnus approximation to calculate the dew point
        alpha = MAGNUS_K2 * self._indoor_temp / (MAGNUS_K3 + self._indoor_temp)
        beta = MAGNUS_K2 * MAGNUS_K3 / (MAGNUS_K3 + self._indoor_temp)

        self._dewpoint = \
            MAGNUS_K3 * (alpha + math.log(self._indoor_hum / 100.0)) / \
            (beta - math.log(self._indoor_hum / 100.0))
        _LOGGER.debug("Dewpoint: %f " + TEMP_CELCIUS, self._dewpoint)

    def _calc_moldindicator(self):
        """ Calculates the humidity at the (cold) calibration point """

        if None in (self._dewpoint, self._calib_value) or \
           self._calib_value == 0:

            _LOGGER.debug("Invalid inputs - dewpoint: %s,"
                          " calibration-Value: %s",
                          self._dewpoint, self._calib_value)
            self._state = "-"
            return

        # first calculate the approximate temperature at the calibration point
        self._crit_temp = \
            self._outdoor_temp + (self._indoor_temp - self._outdoor_temp) / \
            self._calib_value

        _LOGGER.debug(
            "Estimated Critical Temperature: %f " +
            TEMP_CELCIUS, self._crit_temp)

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
            self._state = '{0:.2f}'.format(crit_humidity)

        _LOGGER.debug('Mold indicator humidity: %s ', self._state)

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        """ Returns the name. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return "%"

    @property
    def state(self):
        """ Returns the state of the entity. """
        return self._state

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        if self._dewpoint and self._crit_temp:

            if self._is_metric:
                return {
                    ATTR_DEWPOINT: '{0:.2f}'.format(self._dewpoint) +
                                   ' ' + TEMP_CELCIUS,
                    ATTR_CRITICAL_TEMP: '{0:.2f}'.format(self._crit_temp) +
                                        ' ' + TEMP_CELCIUS,
                }
            else:
                return {
                    ATTR_DEWPOINT: '{0:.2f}'.format(
                        util.temperature.celcius_to_fahrenheit(
                            self._dewpoint)) + ' ' + TEMP_FAHRENHEIT,
                    ATTR_CRITICAL_TEMP: '{0:.2f}'.format(
                        util.temperature.celcius_to_fahrenheit(
                            self._crit_temp)) + ' ' + TEMP_FAHRENHEIT,
                }
