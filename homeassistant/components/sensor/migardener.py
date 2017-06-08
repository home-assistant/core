"""Sensor for monitoring plants with Xiaomi Mi Plant sensors.

To read the sensor data and send it via MQTT,
see https://github.com/ChristianKuehnel/plantgateway
"""

import json
import logging
import asyncio
import voluptuous as vol
from homeassistant.const import (
    CONF_PLATFORM, CONF_NAME, STATE_UNKNOWN, ATTR_BATTERY_LEVEL,
    TEMP_CELSIUS, ATTR_TEMPERATURE, ATTR_SERVICE,
    ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback


_LOGGER = logging.getLogger(__name__)

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


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up MiGardener."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    mi_gardener = MiGardener(hass, config)
    async_add_entities([mi_gardener])

    yield from mqtt.async_subscribe(hass, mi_gardener.state_topic,
                                    mi_gardener.message_received)
    _LOGGER.debug('platform setup completed')
    return True


class MiGardener(Entity):
    """Mi Gardener reads measurements from a
    Xiaomi Mi plant sensor via MQTT.

    It also checks the measurements against
    configurable min and max values.
    """

    READINGS = {
        READING_BATTERY: {
            ATTR_UNIT_OF_MEASUREMENT:  '%',
            'min': CONF_MIN_BATTERY_LEVEL,
            'icon': 'mdi:battery-outline'
        },
        READING_TEMPERATURE: {
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            'min': CONF_MIN_TEMPERATURE,
            'max': CONF_MAX_TEMPERATURE,
            'icon': 'mdi:thermometer'
        },
        READING_MOISTURE: {
            ATTR_UNIT_OF_MEASUREMENT: '%',
            'min': CONF_MIN_MOISTURE,
            'max': CONF_MAX_MOISTURE,
            'icon': 'mdi:water'
        },
        READING_CONDUCTIVITY: {
            ATTR_UNIT_OF_MEASUREMENT: 'µS/cm',
            'min': CONF_MIN_CONDUCTIVITY,
            'max': CONF_MAX_CONDUCTIVITY,
            'icon': 'mdi:emoticon-poop'
        },
        READING_BRIGHTNESS: {
            ATTR_UNIT_OF_MEASUREMENT: 'lux',
            'min': CONF_MIN_BRIGHTNESS,
            'max': CONF_MAX_BRIGHTNESS,
            'icon': 'mdi:white-balance-sunny'
        }
    }

    def __init__(self, hass, config):
        """Default constructor."""
        self._hass = hass
        self._config = config
        self._state = STATE_UNKNOWN
        self._name = config[CONF_NAME]
        self.state_topic = config[CONF_STATE_TOPIC]
        self._battery = None
        self._moisture = None
        self._conductivity = None
        self._temperature = None
        self._brightness = None
        self._icon = None

    @callback
    def message_received(self, topic, payload, qos):
        """A new MQTT message has been received."""
        _LOGGER.debug('Received data: %s', payload)
        data = json.loads(payload)
        self._update_state(data)
        self._hass.async_add_job(self.async_update_ha_state())

    def _update_state(self, data):
        """"Update the state of the class based on the
        data received via MQTT.
        """

        self._battery = int(data[READING_BATTERY])
        self._brightness = int(data[READING_BRIGHTNESS])
        self._moisture = int(data[READING_MOISTURE])
        self._conductivity = int(data[READING_CONDUCTIVITY])
        self._temperature = float(data[READING_TEMPERATURE])

        result = []
        for sensor_name, params in self.READINGS.items():
            value = getattr(self, '_{}'.format(sensor_name))

            if 'min' in params and params['min'] in self._config:
                min_value = self._config[params['min']]
                if value < min_value:
                    result.append('{} low'.format(sensor_name))
                    self._icon = params['icon']

            if 'max' in params and params['max'] in self._config:
                max_value = self._config[params['max']]
                if value > max_value:
                    result.append('{} high'.format(sensor_name))
                    self._icon = params['icon']

        if len(result) == 0:
            self._state = 'ok'
            self._icon = 'mdi:thumb-up'
        else:
            self._state = ', '.join(result)
        _LOGGER.debug('new data processed')

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def state_attributes(self):
        """provide the individual measurements from the
        sensor in the attributes of the device.
        """

        attrib = {
            ATTR_BATTERY_LEVEL: self._battery,
            READING_BRIGHTNESS: self._brightness,
            READING_MOISTURE: self._moisture,
            READING_CONDUCTIVITY: self._conductivity,
            READING_TEMPERATURE: self._temperature,
            ATTR_ICON: self._icon,
        }
        return attrib
