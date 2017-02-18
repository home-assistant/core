"""
Sensor for monitoring plants with Xiaomi Mi Plant sensors
"""

#import logging
import voluptuous as vol
from homeassistant.const import (
    CONF_PLATFORM, CONF_NAME, STATE_UNKNOWN, CONF_UNIT_OF_MEASUREMENT, ATTR_BATTERY_LEVEL, TEMP_CELSIUS, ATTR_TEMPERATURE, ATTR_SERVICE)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
import asyncio

DEFAULT_NAME = 'MiGardener'
DEPENDENCIES = ['mqtt']
CONF_MIN_BATTERY_LEVEL = 'min_{}'.format(ATTR_BATTERY_LEVEL)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_MIN_BATTERY_LEVEL): cv.string,
    vol.Optional(ATTR_SERVICE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up MiGardener"""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    mg = MiGardener(hass,config)

    readings = [
        mg.add_reading('battery',  '%', int),
        mg.add_reading('temperature', TEMP_CELSIUS, float),
        mg.add_reading('moisture',  '%', int),
        mg.add_reading('conductivity', 'µS/cm', int),
        mg.add_reading('brightness', 'lux', int),
    ]

    add_devices([mg])
    add_devices(readings)
    mg.create_group()

class MiGardener(Entity):

    def __init__(self, hass, config):
        self._hass = hass
        self._config = config
        self._state = STATE_UNKNOWN
        self._name = config[CONF_NAME]
        self._state_topic = '{}/+'.format(config[CONF_STATE_TOPIC])
        self._readings = []

    def add_reading(self, name, unit_of_measurement, cast_function):
        r = MiGardenerReading(self._hass, self._config, name, unit_of_measurement, cast_function)
        self._readings.append(name)
        return r

    def create_group(self):
        entity_ids = []
        for reading_name in self._readings:
            entity_ids.append('sensor.{}_{}'.format(self._name, reading_name))
        self._hass.states.set('group.{}'.format(self._name), 'test', attributes={'entity_id': entity_ids})

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
        return self._readings


class MiGardenerReading(Entity):

    def __init__(self, hass, config, name, unit_of_measurement, cast_function):
        self._hass = hass
        self._config = config
        self._name = '{}_{}'.format(config[CONF_NAME],name)
        self._state_topic = '{}/{}'.format(config[CONF_STATE_TOPIC], name)
        self._friendly_name = name
        self._unit_of_measurement = unit_of_measurement
        self._cast_function = cast_function
        self._state = STATE_UNKNOWN
        #self._min_value = config['min_{}'.format(name)] or None
        #self._max_value = config['max_{}'.format(name)] or None

        @callback
        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            self._state = self._cast_function(payload)
            self._hass.async_add_job(self.async_update_ha_state())

        mqtt.subscribe(hass, self._state_topic, message_received)


    @property
    def state(self):
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def friendly_name(self):
        return self._friendly_name

