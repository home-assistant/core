"""
Sensor for monitoring plants with Xiaomi Mi Plant sensors
"""

import logging
import voluptuous as vol
from homeassistant.const import (
    CONF_PLATFORM, CONF_NAME, STATE_UNKNOWN, ATTR_BATTERY_LEVEL, TEMP_CELSIUS, ATTR_TEMPERATURE, ATTR_SERVICE,
    ATTR_UNIT_OF_MEASUREMENT)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
import json
import asyncio

DEFAULT_NAME = 'MiGardener'
DEPENDENCIES = ['mqtt']

READING_BATTERY = 'battery'
READING_TEMPERATURE = ATTR_TEMPERATURE
READING_MOISTURE = 'moisture'
READING_CONDUCTIVITY = 'conductivity'
READING_BRIGHTNESS = 'brightness'
CAST_FUNCTION = 'cast_function'

CONF_MIN_BATTERY_LEVEL = 'min_' + READING_BATTERY
CONF_MIN_TEMPERATURE = 'min_' + READING_TEMPERATURE
CONF_MAX_TEMPERATURE = 'max_' + READING_TEMPERATURE
CONF_MIN_MOISTURE = 'min_' + READING_MOISTURE
CONF_MAX_MOISTURE = 'max_' + READING_MOISTURE
CONF_MIN_CONDUCTIVITY = 'min_' + READING_CONDUCTIVITY
CONF_MAX_CONDUCTIVITY = 'max_' + READING_CONDUCTIVITY
CONF_MIN_BRIGHTNESS = 'min_' + READING_BRIGHTNESS
CONF_MAX_BRIGHTNESS = 'max_' + READING_BRIGHTNESS


PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(ATTR_SERVICE): cv.string,
    vol.Optional(CONF_MIN_BATTERY_LEVEL): cv.positive_int,
    vol.Optional(CONF_MIN_TEMPERATURE): cv.small_float,
    vol.Optional(CONF_MAX_TEMPERATURE): cv.small_float,
    vol.Optional(CONF_MIN_MOISTURE): cv.positive_int,
    vol.Optional(CONF_MAX_MOISTURE): cv.positive_int,
    vol.Optional(CONF_MIN_CONDUCTIVITY): cv.positive_int,
    vol.Optional(CONF_MAX_CONDUCTIVITY): cv.positive_int,
    vol.Optional(CONF_MIN_BRIGHTNESS): cv.positive_int,
    vol.Optional(CONF_MAX_BRIGHTNESS): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up MiGardener"""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    mg = MiGardener(hass, config)
    add_devices([mg])


class MiGardener(Entity):


    READINGS =  {
        READING_BATTERY: {
            ATTR_UNIT_OF_MEASUREMENT:  '%',
            CAST_FUNCTION:int,
            'min':CONF_MIN_BATTERY_LEVEL},
        READING_TEMPERATURE: {
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            CAST_FUNCTION:float,
            'min': CONF_MIN_TEMPERATURE ,
            'max': CONF_MAX_TEMPERATURE,
        },
        READING_MOISTURE: {
            ATTR_UNIT_OF_MEASUREMENT: '%',
            CAST_FUNCTION: int,
            'min': CONF_MIN_MOISTURE,
            'max': CONF_MAX_MOISTURE,
        },
        READING_CONDUCTIVITY: {
            ATTR_UNIT_OF_MEASUREMENT: 'µS/cm',
            CAST_FUNCTION: int,
            'min': CONF_MIN_CONDUCTIVITY,
            'max': CONF_MAX_CONDUCTIVITY,
        },
        READING_BRIGHTNESS: {
            ATTR_UNIT_OF_MEASUREMENT: 'lux',
            CAST_FUNCTION: int,
            'min': CONF_MIN_BRIGHTNESS,
            'max': CONF_MAX_BRIGHTNESS,
        }
    }

    def __init__(self, hass, config):
        self._hass = hass
        self._config = config
        self._state = STATE_UNKNOWN
        self._name = config[CONF_NAME]
        self._state_topic = config[CONF_STATE_TOPIC]
        self._attrib = dict()
        self._create_group()

        @callback
        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            data = json.loads(payload)
            for sensor_name,params in self.READINGS.items():
                value = params[CAST_FUNCTION](data[sensor_name])
                self._set_sensor(sensor_name, value)
            self._hass.async_add_job(self.check_state())

        mqtt.subscribe(hass, self._state_topic, message_received)

    def _create_group(self):
        entity_ids = [self._sensor_entity_id()]
        for sensor_name in self.READINGS:
            entity_ids.append(self._sensor_entity_id(sensor_name))
        self._hass.states.set('group.{}'.format(self._name), STATE_UNKNOWN, attributes={'entity_id': entity_ids})

    def _sensor_entity_id(self, sensor_name=None):
        if sensor_name is None:
            return 'sensor.{}'.format(self._name).lower()
        return 'sensor.{}_{}'.format(self._name, sensor_name).lower()

    def _set_sensor(self, sensor_name, value):
        attrib = {
            ATTR_UNIT_OF_MEASUREMENT : self.READINGS[sensor_name][ATTR_UNIT_OF_MEASUREMENT],
        }
        self._hass.states.async_set(self._sensor_entity_id(sensor_name), value, attributes=attrib)

    @asyncio.coroutine
    def check_state(self,):
        result = []
        for sensor_name,params in self.READINGS.items():
            state = self._hass.states.get(self._sensor_entity_id(sensor_name))
            value = params[CAST_FUNCTION](state.state)

            if 'min' in params and params['min'] in self._config:
                min_value = self._config[params['min']]
                if value < min_value:
                    result.append('{} low'.format(sensor_name))

            if 'max' in params and params['max'] in self._config:
                max_value = self._config[params['max']]
                if value > max_value:
                    result.append('{} high'.format(sensor_name))


        if len(result) == 0:
            self._state = 'ok'
        else:
            self._state = ', '.join(result)
        self._hass.async_add_job(self.async_update_ha_state())


    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    # @property
    # def unit_of_measurement(self):
    #     """Return the unit this state is expressed in."""
    #     return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def state_attributes(self):
        return self._attrib
