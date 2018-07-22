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
from homeassistant.util import dt as dt_util
from homeassistant.components.recorder.util import session_scope, execute

_LOGGER = logging.getLogger(__name__)

ATTR_SAMPLING_SIZE = 'sampling_size'
ATTR_COUNT = 'count'
ATTR_MEAN = 'mean'
ATTR_MEDIAN = 'median'
ATTR_STANDARD_DEVIATION = 'standard_deviation'
ATTR_VARIANCE = 'variance'
ATTR_TOTAL = 'total'
ATTR_MAX_VALUE = 'max_value'
ATTR_MIN_VALUE = 'min_value'
ATTR_MIN_AGE = 'min_age'
ATTR_MAX_AGE = 'max_age'
ATTR_CHANGE = 'change'
ATTR_AVERAGE_CHANGE = 'average_change'
ATTR_CHANGE_RATE = 'change_rate'

CONF_SAMPLING_SIZE = 'sampling_size'
CONF_MAX_AGE = 'max_age'

DEFAULT_NAME = 'Stats'
DEFAULT_SIZE = 20
ICON = 'mdi:calculator'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SAMPLING_SIZE, default=DEFAULT_SIZE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_MAX_AGE): cv.time_period
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the Statistics sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    sampling_size = config.get(CONF_SAMPLING_SIZE)
    max_age = config.get(CONF_MAX_AGE, None)

    async_add_entities(
        [StatisticsSensor(hass, entity_id, name, sampling_size, max_age)],
        True)
    return True


class StatisticsSensor(Entity):
    """Representation of a Statistics sensor."""

    def __init__(self, hass, entity_id, name, sampling_size, max_age):
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
        self._max_age = max_age
        self._unit_of_measurement = None
        self.states = deque(maxlen=self._sampling_size)
        self.ages = deque(maxlen=self._sampling_size)

        self.count = 0
        self.mean = self.median = self.stdev = self.variance = STATE_UNKNOWN
        self.total = self.min = self.max = STATE_UNKNOWN
        self.min_age = self.max_age = dt_util.utcnow()
        self.change = self.average_change = STATE_UNKNOWN
        self.change_rate = STATE_UNKNOWN

        if 'recorder' in self._hass.config.components:
            # only use the database if it's configured
            hass.async_add_job(self._initialize_from_database)

        @callback
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT)

            self._add_state_to_queue(new_state)

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_stats_sensor_state_listener)

    def _add_state_to_queue(self, new_state):
        try:
            self.states.append(float(new_state.state))
            self.ages.append(new_state.last_updated)
        except ValueError:
            pass

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
                ATTR_SAMPLING_SIZE: self._sampling_size,
                ATTR_COUNT: self.count,
                ATTR_MEAN: self.mean,
                ATTR_MEDIAN: self.median,
                ATTR_STANDARD_DEVIATION: self.stdev,
                ATTR_VARIANCE: self.variance,
                ATTR_TOTAL: self.total,
                ATTR_MIN_VALUE: self.min,
                ATTR_MAX_VALUE: self.max,
                ATTR_MIN_AGE: self.min_age,
                ATTR_MAX_AGE: self.max_age,
                ATTR_CHANGE: self.change,
                ATTR_AVERAGE_CHANGE: self.average_change,
                ATTR_CHANGE_RATE: self.change_rate,
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def _purge_old(self):
        """Remove states which are older than self._max_age."""
        now = dt_util.utcnow()

        while self.ages and (now - self.ages[0]) > self._max_age:
            self.ages.popleft()
            self.states.popleft()

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        if self._max_age is not None:
            self._purge_old()

        self.count = len(self.states)

        if not self.is_binary:
            try:  # require only one data point
                self.mean = round(statistics.mean(self.states), 2)
                self.median = round(statistics.median(self.states), 2)
            except statistics.StatisticsError as err:
                _LOGGER.debug(err)
                self.mean = self.median = STATE_UNKNOWN

            try:  # require at least two data points
                self.stdev = round(statistics.stdev(self.states), 2)
                self.variance = round(statistics.variance(self.states), 2)
            except statistics.StatisticsError as err:
                _LOGGER.debug(err)
                self.stdev = self.variance = STATE_UNKNOWN

            if len(self.states) > 0:
                self.total = round(sum(self.states), 2)
                self.min = min(self.states)
                self.max = max(self.states)
                self.min_age = min(self.ages)
                self.max_age = max(self.ages)
                self.change = self.states[-1] - self.states[0]
                self.average_change = self.change
                self.change_rate = 0

                if len(self.states) > 1:
                    self.average_change /= len(self.states) - 1

                    time_diff = (self.ages[-1] - self.ages[0]).total_seconds()
                    if time_diff > 0:
                        self.change_rate = self.average_change / time_diff

            else:
                self.total = self.min = self.max = STATE_UNKNOWN
                self.max_age = self.min_age = dt_util.utcnow()
                self.change = self.average_change = STATE_UNKNOWN
                self.change_rate = STATE_UNKNOWN

    @asyncio.coroutine
    def _initialize_from_database(self):
        """Initialize the list of states from the database.

        The query will get the list of states in DESCENDING order so that we
        can limit the result to self._sample_size. Afterwards reverse the
        list so that we get it in the right order again.
        """
        from homeassistant.components.recorder.models import States
        _LOGGER.debug("initializing values for %s from the database",
                      self.entity_id)

        with session_scope(hass=self._hass) as session:
            query = session.query(States)\
                .filter(States.entity_id == self._entity_id.lower())\
                .order_by(States.last_updated.desc())\
                .limit(self._sampling_size)
            states = execute(query)

        for state in reversed(states):
            self._add_state_to_queue(state)

        _LOGGER.debug("initializing from database completed")
