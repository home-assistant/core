"""
Support for statistics for sensor values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.statistics/
"""
import asyncio
import logging
import statistics
from collections import deque

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, STATE_UNKNOWN, ATTR_UNIT_OF_MEASUREMENT)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

ATTR_AVERAGE_CHANGE = 'average_change'
ATTR_CHANGE = 'change'
ATTR_COUNT = 'count'
ATTR_MAX_VALUE = 'max_value'
ATTR_MIN_VALUE = 'min_value'
ATTR_MEAN = 'mean'
ATTR_MEDIAN = 'median'
ATTR_VARIANCE = 'variance'
ATTR_STANDARD_DEVIATION = 'standard_deviation'
ATTR_SAMPLING_SIZE = 'sampling_size'
ATTR_TOTAL = 'total'

CONF_SAMPLING_SIZE = 'sampling_size'
DEFAULT_NAME = 'Stats'
DEFAULT_SIZE = 20
ICON = 'mdi:calculator'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SAMPLING_SIZE, default=DEFAULT_SIZE): cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Statistics sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    sampling_size = config.get(CONF_SAMPLING_SIZE)

    async_add_devices(
        [StatisticsSensor(hass, entity_id, name, sampling_size)], True)
    return True


class StatisticsSensor(Entity):
    """Representation of a Statistics sensor."""

    def __init__(self, hass, entity_id, name, sampling_size):
        """Initialize the Statistics sensor."""
        self._hass = hass
        self._entity_id = entity_id
        self.is_binary = True if self._entity_id.split('.')[0] == \
            'binary_sensor' else False
        if not self.is_binary:
            self._name = '{} {}'.format(name, ATTR_MEAN)
        else:
            self._name = '{} {}'.format(name, ATTR_COUNT)
        self._sampling_size = sampling_size
        self._unit_of_measurement = None
        if self._sampling_size == 0:
            self.states = deque()
        else:
            self.states = deque(maxlen=self._sampling_size)
        self.median = self.mean = self.variance = self.stdev = 0
        self.min = self.max = self.total = self.count = 0
        self.average_change = self.change = 0

        @callback
        # pylint: disable=invalid-name
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT)

            try:
                self.states.append(float(new_state.state))
                self.count = self.count + 1
            except ValueError:
                self.count = self.count + 1

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_stats_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.mean if not self.is_binary else self.count

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement if not self.is_binary else None

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if not self.is_binary:
            return {
                ATTR_MEAN: self.mean,
                ATTR_COUNT: self.count,
                ATTR_MAX_VALUE: self.max,
                ATTR_MEDIAN: self.median,
                ATTR_MIN_VALUE: self.min,
                ATTR_SAMPLING_SIZE: 'unlimited' if self._sampling_size is
                                    0 else self._sampling_size,
                ATTR_STANDARD_DEVIATION: self.stdev,
                ATTR_TOTAL: self.total,
                ATTR_VARIANCE: self.variance,
                ATTR_CHANGE: self.change,
                ATTR_AVERAGE_CHANGE: self.average_change,
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        if not self.is_binary:
            try:
                self.mean = round(statistics.mean(self.states), 2)
                self.median = round(statistics.median(self.states), 2)
                self.stdev = round(statistics.stdev(self.states), 2)
                self.variance = round(statistics.variance(self.states), 2)
            except statistics.StatisticsError as err:
                _LOGGER.warning(err)
                self.mean = self.median = STATE_UNKNOWN
                self.stdev = self.variance = STATE_UNKNOWN
            if self.states:
                self.total = round(sum(self.states), 2)
                self.min = min(self.states)
                self.max = max(self.states)
                self.change = self.states[-1] - self.states[0]
                self.average_change = self.change
                if len(self.states) > 1:
                    self.average_change /= len(self.states) - 1
            else:
                self.min = self.max = self.total = STATE_UNKNOWN
                self.average_change = self.change = STATE_UNKNOWN
