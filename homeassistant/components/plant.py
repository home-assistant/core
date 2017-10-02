"""
Component to monitor plants.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plant/
"""
import logging
import asyncio
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.const import (
    STATE_OK, STATE_PROBLEM, STATE_UNKNOWN, TEMP_CELSIUS, ATTR_TEMPERATURE,
    CONF_SENSORS, ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON)
from homeassistant.components import group
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.components.recorder.util import session_scope, execute

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
CONF_GROUP_NAME = 'group_name'
CONF_CHECK_DAYS = 'check_days'

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
    vol.Optional(CONF_GROUP_NAME): cv.string,
    vol.Optional(CONF_CHECK_DAYS): cv.positive_int,
})

DOMAIN = 'plant'
DEPENDENCIES = ['zone', 'group', 'recorder']

GROUP_NAME_ALL_PLANTS = 'all plants'
ENTITY_ID_ALL_PLANTS = group.ENTITY_ID_FORMAT.format('all_plants')

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        cv.string: PLANT_SCHEMA
    },
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Plant component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass,
                                group_name=GROUP_NAME_ALL_PLANTS)

    entities = []
    for plant_name, plant_config in config[DOMAIN].items():
        _LOGGER.info("Added plant %s", plant_name)
        group_name = None
        if CONF_GROUP_NAME in plant_config and \
                plant_config[CONF_GROUP_NAME] is not None:
            group_name = plant_config[CONF_GROUP_NAME]
            hass.components.group.set_group(group_name)
            _LOGGER.debug("Added plant group %s for plant %s",
                          group_name, plant_name)
        entity = Plant(plant_name, plant_config, group_name)
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
            # minimum brightness is checked separately
            'max': CONF_MAX_BRIGHTNESS,
            'icon': 'mdi:white-balance-sunny'
        }
    }

    def __init__(self, name, config, group_name=None):
        """Initialize the Plant component."""
        self._config = config
        self._group_name = group_name
        self._sensormap = dict()
        self._readingmap = dict()
        for reading, entity_id in config['sensors'].items():
            self._sensormap[entity_id] = reading
            self._readingmap[reading] = entity_id
        self._state = STATE_UNKNOWN
        self._name = name
        self._battery = None
        self._moisture = None
        self._conductivity = None
        self._temperature = None
        self._brightness = None
        self._icon = 'mdi:help-circle'
        self._problems = PROBLEM_NONE

        self._conf_check_days = 3  # default check interval: 3 days
        self._brightness_updated = True  # on startup check the brightness
        self._max_brightness_over_days = None
        self._brightness_problem = []
        if CONF_CHECK_DAYS in self._config:
            self._conf_check_days = self._config[CONF_CHECK_DAYS]

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
            self._brightness_updated = True
        else:
            raise _LOGGER.error("Unknown reading from sensor %s: %s",
                                entity_id, value)
        self._update_state()

    def _update_state(self):
        """Update the state of the class based sensor data."""
        self.check_brightness()
        result = list(self._brightness_problem)
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

        if result:
            self._state = STATE_PROBLEM
            self._problems = ', '.join(result)
        else:
            self._state = STATE_OK
            self._icon = 'mdi:thumb-up'
            self._problems = PROBLEM_NONE
        _LOGGER.debug("New data processed")
        self.async_schedule_update_ha_state()

    def check_brightness(self):
        """
        Check brightness levels over a history of several days.

        It usually does not make sense to check the minimum brightness now as
        it might be night. So we need to check this over several days to see if
        one of those days was bright enough.

        As this operation is quite expensive, we should not run it so
        frequently. Thus we only check when the brightness really changed
        (ie self._brightness_updated == True). The result of the last check
        is cached in self._brightness_problem.
        """
        from homeassistant.components.recorder.models import States

        if CONF_MIN_BRIGHTNESS not in self._config or \
                not self._brightness_updated:
            # only run this if there is a minimum brightness level defined
            return

        end_date = datetime.now()
        start_date = end_date - timedelta(days=self._conf_check_days)
        _LOGGER.debug("Checking brightness history")
        entity_id = self._readingmap[READING_BRIGHTNESS]
        brightness_values = []
        with session_scope(hass=self.hass) as session:
            query = session.query(States).filter(
                (States.entity_id == entity_id.lower()) and
                (States.last_updated > start_date) and
                (States.last_updated <= end_date)
            )
            states = execute(query)

            for state in states:
                # filter out all None, NaN and "unknown" states
                # only keep real values
                try:
                    brightness_values.append(int(state.state))
                except ValueError:
                    pass
        self._brightness_updated = False
        self._max_brightness_over_days = max(brightness_values)
        if self._max_brightness_over_days < self._config[CONF_MIN_BRIGHTNESS]:
            self._brightness_problem = [
                'maximum brightness of {} lux too low over last '
                '{} days'.format(
                    self._max_brightness_over_days, self._conf_check_days)
            ]
        else:
            self._brightness_problem = []

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

        if self._max_brightness_over_days is not None:
            attrib['max brightness over {} days'.format(
                self._conf_check_days)] = self._max_brightness_over_days

        return attrib

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Create a group with all sensors.

        This must be run after the component was created to that we get the
        valid entity_id.
        """
        if self._group_name is not None:
            members = [self.entity_id]
            members.extend(list(self._config[CONF_SENSORS].values()))
            self.hass.components.group.set_group(self._group_name,
                                                 entity_ids=members)
