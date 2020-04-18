"""Support for statistics for sensor values."""
from collections import deque
import logging
import statistics

import voluptuous as vol

from homeassistant.components.recorder.models import States
from homeassistant.components.recorder.util import execute, session_scope
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change,
)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_AVERAGE_CHANGE = "average_change"
ATTR_CHANGE = "change"
ATTR_CHANGE_RATE = "change_rate"
ATTR_COUNT = "count"
ATTR_MAX_AGE = "max_age"
ATTR_MAX_VALUE = "max_value"
ATTR_MEAN = "mean"
ATTR_MEDIAN = "median"
ATTR_MIN_AGE = "min_age"
ATTR_MIN_VALUE = "min_value"
ATTR_SAMPLING_SIZE = "sampling_size"
ATTR_STANDARD_DEVIATION = "standard_deviation"
ATTR_TOTAL = "total"
ATTR_VARIANCE = "variance"

CONF_SAMPLING_SIZE = "sampling_size"
CONF_MAX_AGE = "max_age"
CONF_PRECISION = "precision"

DEFAULT_NAME = "Stats"
DEFAULT_SIZE = 20
DEFAULT_PRECISION = 2
ICON = "mdi:calculator"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SAMPLING_SIZE, default=DEFAULT_SIZE): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_MAX_AGE): cv.time_period,
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.Coerce(int),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Statistics sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    sampling_size = config.get(CONF_SAMPLING_SIZE)
    max_age = config.get(CONF_MAX_AGE)
    precision = config.get(CONF_PRECISION)

    async_add_entities(
        [StatisticsSensor(entity_id, name, sampling_size, max_age, precision)], True
    )

    return True


class StatisticsSensor(Entity):
    """Representation of a Statistics sensor."""

    def __init__(self, entity_id, name, sampling_size, max_age, precision):
        """Initialize the Statistics sensor."""
        self._entity_id = entity_id
        self.is_binary = self._entity_id.split(".")[0] == "binary_sensor"
        self._name = name
        self._sampling_size = sampling_size
        self._max_age = max_age
        self._precision = precision
        self._unit_of_measurement = None
        self.states = deque(maxlen=self._sampling_size)
        self.ages = deque(maxlen=self._sampling_size)

        self.count = 0
        self.mean = self.median = self.stdev = self.variance = None
        self.total = self.min = self.max = None
        self.min_age = self.max_age = None
        self.change = self.average_change = self.change_rate = None
        self._update_listener = None

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            )

            self._add_state_to_queue(new_state)

            self.async_schedule_update_ha_state(True)

        @callback
        def async_stats_sensor_startup(event):
            """Add listener and get recorded state."""
            _LOGGER.debug("Startup for %s", self.entity_id)

            async_track_state_change(
                self.hass, self._entity_id, async_stats_sensor_state_listener
            )

            if "recorder" in self.hass.config.components:
                # Only use the database if it's configured
                self.hass.async_create_task(self._async_initialize_from_database())

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_stats_sensor_startup
        )

    def _add_state_to_queue(self, new_state):
        """Add the state to the queue."""
        if new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            return

        try:
            if self.is_binary:
                self.states.append(new_state.state)
            else:
                self.states.append(float(new_state.state))

            self.ages.append(new_state.last_updated)
        except ValueError:
            _LOGGER.error(
                "%s: parsing error, expected number and received %s",
                self.entity_id,
                new_state.state,
            )

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

        _LOGGER.debug(
            "%s: purging records older then %s(%s)",
            self.entity_id,
            dt_util.as_local(now - self._max_age),
            self._max_age,
        )

        while self.ages and (now - self.ages[0]) > self._max_age:
            _LOGGER.debug(
                "%s: purging record with datetime %s(%s)",
                self.entity_id,
                dt_util.as_local(self.ages[0]),
                (now - self.ages[0]),
            )
            self.ages.popleft()
            self.states.popleft()

    def _next_to_purge_timestamp(self):
        """Find the timestamp when the next purge would occur."""
        if self.ages and self._max_age:
            # Take the oldest entry from the ages list and add the configured max_age.
            # If executed after purging old states, the result is the next timestamp
            # in the future when the oldest state will expire.
            return self.ages[0] + self._max_age
        return None

    async def async_update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("%s: updating statistics.", self.entity_id)
        if self._max_age is not None:
            self._purge_old()

        self.count = len(self.states)

        if not self.is_binary:
            try:  # require only one data point
                self.mean = round(statistics.mean(self.states), self._precision)
                self.median = round(statistics.median(self.states), self._precision)
            except statistics.StatisticsError as err:
                _LOGGER.debug("%s: %s", self.entity_id, err)
                self.mean = self.median = STATE_UNKNOWN

            try:  # require at least two data points
                self.stdev = round(statistics.stdev(self.states), self._precision)
                self.variance = round(statistics.variance(self.states), self._precision)
            except statistics.StatisticsError as err:
                _LOGGER.debug("%s: %s", self.entity_id, err)
                self.stdev = self.variance = STATE_UNKNOWN

            if self.states:
                self.total = round(sum(self.states), self._precision)
                self.min = round(min(self.states), self._precision)
                self.max = round(max(self.states), self._precision)

                self.min_age = self.ages[0]
                self.max_age = self.ages[-1]

                self.change = self.states[-1] - self.states[0]
                self.average_change = self.change
                self.change_rate = 0

                if len(self.states) > 1:
                    self.average_change /= len(self.states) - 1

                    time_diff = (self.max_age - self.min_age).total_seconds()
                    if time_diff > 0:
                        self.change_rate = self.change / time_diff

                self.change = round(self.change, self._precision)
                self.average_change = round(self.average_change, self._precision)
                self.change_rate = round(self.change_rate, self._precision)

            else:
                self.total = self.min = self.max = STATE_UNKNOWN
                self.min_age = self.max_age = dt_util.utcnow()
                self.change = self.average_change = STATE_UNKNOWN
                self.change_rate = STATE_UNKNOWN

        # If max_age is set, ensure to update again after the defined interval.
        next_to_purge_timestamp = self._next_to_purge_timestamp()
        if next_to_purge_timestamp:
            _LOGGER.debug(
                "%s: scheduling update at %s", self.entity_id, next_to_purge_timestamp
            )
            if self._update_listener:
                self._update_listener()
                self._update_listener = None

            @callback
            def _scheduled_update(now):
                """Timer callback for sensor update."""
                _LOGGER.debug("%s: executing scheduled update", self.entity_id)
                self.async_schedule_update_ha_state(True)
                self._update_listener = None

            self._update_listener = async_track_point_in_utc_time(
                self.hass, _scheduled_update, next_to_purge_timestamp
            )

    async def _async_initialize_from_database(self):
        """Initialize the list of states from the database.

        The query will get the list of states in DESCENDING order so that we
        can limit the result to self._sample_size. Afterwards reverse the
        list so that we get it in the right order again.

        If MaxAge is provided then query will restrict to entries younger then
        current datetime - MaxAge.
        """

        _LOGGER.debug("%s: initializing values from the database", self.entity_id)

        with session_scope(hass=self.hass) as session:
            query = session.query(States).filter(
                States.entity_id == self._entity_id.lower()
            )

            if self._max_age is not None:
                records_older_then = dt_util.utcnow() - self._max_age
                _LOGGER.debug(
                    "%s: retrieve records not older then %s",
                    self.entity_id,
                    records_older_then,
                )
                query = query.filter(States.last_updated >= records_older_then)
            else:
                _LOGGER.debug("%s: retrieving all records.", self.entity_id)

            query = query.order_by(States.last_updated.desc()).limit(
                self._sampling_size
            )
            states = execute(query)

        for state in reversed(states):
            self._add_state_to_queue(state)

        self.async_schedule_update_ha_state(True)

        _LOGGER.debug("%s: initializing from database completed", self.entity_id)
