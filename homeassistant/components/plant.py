"""
Component to monitor plants.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plant/
"""
import logging
import asyncio

import voluptuous as vol

from homeassistant.const import (
    STATE_UNKNOWN, TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_SENSORS,
    ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'plant'

READING_BATTERY = 'battery'
READING_TEMPERATURE = ATTR_TEMPERATURE
READING_MOISTURE = 'moisture'
READING_CONDUCTIVITY = 'conductivity'
READING_BRIGHTNESS = 'brightness'

ATTR_PROBLEM = 'problem'
PROBLEM_NONE = 'none'

CONF_MIN_BATTERY_LEVEL = 'min_' + READING_BATTERY
CONF_MIN_TEMPERATURE = 'min_' + READING_TEMPERATURE
CONF_MAX_TEMPERATURE = 'max_' + READING_TEMPERATURE
CONF_MIN_MOISTURE = 'min_' + READING_MOISTURE
CONF_MAX_MOISTURE = 'max_' + READING_MOISTURE
CONF_MIN_CONDUCTIVITY = 'min_' + READING_CONDUCTIVITY
CONF_MAX_CONDUCTIVITY = 'max_' + READING_CONDUCTIVITY
CONF_MIN_BRIGHTNESS = 'min_' + READING_BRIGHTNESS
CONF_MAX_BRIGHTNESS = 'max_' + READING_BRIGHTNESS

CONF_SENSOR_BATTERY_LEVEL = READING_BATTERY
CONF_SENSOR_MOISTURE = READING_MOISTURE
CONF_SENSOR_CONDUCTIVITY = READING_CONDUCTIVITY
CONF_SENSOR_TEMPERATURE = READING_TEMPERATURE
CONF_SENSOR_BRIGHTNESS = READING_BRIGHTNESS

SCHEMA_SENSORS = vol.Schema({
    vol.Optional(CONF_SENSOR_BATTERY_LEVEL): cv.entity_id,
    vol.Optional(CONF_SENSOR_MOISTURE): cv.entity_id,
    vol.Optional(CONF_SENSOR_CONDUCTIVITY): cv.entity_id,
    vol.Optional(CONF_SENSOR_TEMPERATURE): cv.entity_id,
    vol.Optional(CONF_SENSOR_BRIGHTNESS): cv.entity_id,
})

PLANT_SCHEMA = vol.Schema({
    vol.Required(CONF_SENSORS): vol.Schema(SCHEMA_SENSORS),
    vol.Optional(CONF_MIN_BATTERY_LEVEL): cv.positive_int,
    vol.Optional(CONF_MIN_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_MAX_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_MIN_MOISTURE): cv.positive_int,
    vol.Optional(CONF_MAX_MOISTURE): cv.positive_int,
    vol.Optional(CONF_MIN_CONDUCTIVITY): cv.positive_int,
    vol.Optional(CONF_MAX_CONDUCTIVITY): cv.positive_int,
    vol.Optional(CONF_MIN_BRIGHTNESS): cv.positive_int,
    vol.Optional(CONF_MAX_BRIGHTNESS): cv.positive_int,
})

DOMAIN = 'plant'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        cv.string: PLANT_SCHEMA
    },
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Plant component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []
    for plant_name, plant_config in config[DOMAIN].items():
        _LOGGER.info("Added plant %s", plant_name)
        entity = Plant(plant_name, plant_config)
        sensor_entity_ids = list(plant_config[CONF_SENSORS].values())
        _LOGGER.debug("Subscribing to entity_ids %s", sensor_entity_ids)
        async_track_state_change(hass, sensor_entity_ids, entity.state_changed)
        entities.append(entity)

    yield from component.async_add_entities(entities)

    return True


class Plant(Entity):
    """Plant monitors the well-being of a plant.

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

    def __init__(self, name, config):
        """Initialize the Plant component."""
        self._config = config
        self._sensormap = dict()
        for reading, entity_id in config['sensors'].items():
            self._sensormap[entity_id] = reading
        self._state = STATE_UNKNOWN
        self._name = name
        self._battery = None
        self._moisture = None
        self._conductivity = None
        self._temperature = None
        self._brightness = None
        self._icon = 'mdi:help-circle'
        self._problems = PROBLEM_NONE

    @callback
    def state_changed(self, entity_id, _, new_state):
        """Update the sensor status.

        This callback is triggered, when the sensor state changes.
        """
        value = new_state.state
        _LOGGER.debug("Received callback from %s with value %s",
                      entity_id, value)
        if value == STATE_UNKNOWN:
            return

        reading = self._sensormap[entity_id]
        if reading == READING_MOISTURE:
            self._moisture = int(value)
        elif reading == READING_BATTERY:
            self._battery = int(value)
        elif reading == READING_TEMPERATURE:
            self._temperature = float(value)
        elif reading == READING_CONDUCTIVITY:
            self._conductivity = int(value)
        elif reading == READING_BRIGHTNESS:
            self._brightness = int(value)
        else:
            raise _LOGGER.error("Unknown reading from sensor %s: %s",
                                entity_id, value)
        self._update_state()

    def _update_state(self):
        """Update the state of the class based sensor data."""
        result = []
        for sensor_name in self._sensormap.values():
            params = self.READINGS[sensor_name]
            value = getattr(self, '_{}'.format(sensor_name))
            if value is not None:
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
            self._problems = PROBLEM_NONE
        else:
            self._state = 'problem'
            self._problems = ','.join(result)
        _LOGGER.debug("New data processed")
        self.hass.async_add_job(self.async_update_ha_state())

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
        """Return the attributes of the entity.

        Provide the individual measurements from the
        sensor in the attributes of the device.
        """
        attrib = {
            ATTR_ICON: self._icon,
            ATTR_PROBLEM: self._problems,
        }

        for reading in self._sensormap.values():
            attrib[reading] = getattr(self, '_{}'.format(reading))

        return attrib
