"""Support for statistics for sensor values."""
from collections import deque
import contextlib
import logging
import statistics

import voluptuous as vol

from homeassistant.components.recorder.models import States
from homeassistant.components.recorder.util import execute, session_scope
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.start import async_at_start
from homeassistant.util import dt as dt_util

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

STAT_AVERAGE_CHANGE = "average_change"
STAT_CHANGE = "change"
STAT_CHANGE_RATE = "change_rate"
STAT_COUNT = "count"
STAT_MAX_AGE = "max_age"
STAT_MAX_VALUE = "max_value"
STAT_MEAN = "mean"
STAT_MEDIAN = "median"
STAT_MIN_AGE = "min_age"
STAT_MIN_VALUE = "min_value"
STAT_QUANTILES = "quantiles"
STAT_STANDARD_DEVIATION = "standard_deviation"
STAT_TOTAL = "total"
STAT_VARIANCE = "variance"

CONF_STATE_CHARACTERISTIC = "state_characteristic"
CONF_SAMPLES_MAX_BUFFER_SIZE = "sampling_size"
CONF_MAX_AGE = "max_age"
CONF_PRECISION = "precision"
CONF_QUANTILE_INTERVALS = "quantile_intervals"
CONF_QUANTILE_METHOD = "quantile_method"

DEFAULT_NAME = "Stats"
DEFAULT_BUFFER_SIZE = 20
DEFAULT_PRECISION = 2
DEFAULT_QUANTILE_INTERVALS = 4
DEFAULT_QUANTILE_METHOD = "exclusive"
ICON = "mdi:calculator"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_STATE_CHARACTERISTIC, default=STAT_MEAN): vol.In(
            [
                STAT_AVERAGE_CHANGE,
                STAT_CHANGE,
                STAT_CHANGE_RATE,
                STAT_COUNT,
                STAT_MAX_AGE,
                STAT_MAX_VALUE,
                STAT_MEAN,
                STAT_MEDIAN,
                STAT_MIN_AGE,
                STAT_MIN_VALUE,
                STAT_QUANTILES,
                STAT_STANDARD_DEVIATION,
                STAT_TOTAL,
                STAT_VARIANCE,
            ]
        ),
        vol.Optional(
            CONF_SAMPLES_MAX_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(CONF_MAX_AGE): cv.time_period,
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.Coerce(int),
        vol.Optional(
            CONF_QUANTILE_INTERVALS, default=DEFAULT_QUANTILE_INTERVALS
        ): vol.All(vol.Coerce(int), vol.Range(min=2)),
        vol.Optional(CONF_QUANTILE_METHOD, default=DEFAULT_QUANTILE_METHOD): vol.In(
            ["exclusive", "inclusive"]
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Statistics sensor."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    async_add_entities(
        [
            StatisticsSensor(
                source_entity_id=config.get(CONF_ENTITY_ID),
                name=config.get(CONF_NAME),
                state_characteristic=config.get(CONF_STATE_CHARACTERISTIC),
                samples_max_buffer_size=config.get(CONF_SAMPLES_MAX_BUFFER_SIZE),
                samples_max_age=config.get(CONF_MAX_AGE),
                precision=config.get(CONF_PRECISION),
                quantile_intervals=config.get(CONF_QUANTILE_INTERVALS),
                quantile_method=config.get(CONF_QUANTILE_METHOD),
            )
        ],
        True,
    )
    return True


class StatisticsSensor(SensorEntity):
    """Representation of a Statistics sensor."""

    def __init__(
        self,
        source_entity_id,
        name,
        state_characteristic,
        samples_max_buffer_size,
        samples_max_age,
        precision,
        quantile_intervals,
        quantile_method,
    ):
        """Initialize the Statistics sensor."""
        self._source_entity_id = source_entity_id
        self.is_binary = self._source_entity_id.split(".")[0] == "binary_sensor"
        self._name = name
        self._available = False
        self._state_characteristic = state_characteristic
        self._samples_max_buffer_size = samples_max_buffer_size
        self._samples_max_age = samples_max_age
        self._precision = precision
        self._quantile_intervals = quantile_intervals
        self._quantile_method = quantile_method
        self._unit_of_measurement = None
        self.states = deque(maxlen=self._samples_max_buffer_size)
        self.ages = deque(maxlen=self._samples_max_buffer_size)
        self.attr = {
            STAT_COUNT: 0,
            STAT_TOTAL: None,
            STAT_MEAN: None,
            STAT_MEDIAN: None,
            STAT_STANDARD_DEVIATION: None,
            STAT_VARIANCE: None,
            STAT_MIN_VALUE: None,
            STAT_MAX_VALUE: None,
            STAT_MIN_AGE: None,
            STAT_MAX_AGE: None,
            STAT_CHANGE: None,
            STAT_AVERAGE_CHANGE: None,
            STAT_CHANGE_RATE: None,
            STAT_QUANTILES: None,
        }
        self._update_listener = None

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def async_stats_sensor_state_listener(event):
            """Handle the sensor state changes."""
            if (new_state := event.data.get("new_state")) is None:
                return
            self._add_state_to_queue(new_state)
            self.async_schedule_update_ha_state(True)

        @callback
        def async_stats_sensor_startup(_):
            """Add listener and get recorded state."""
            _LOGGER.debug("Startup for %s", self.entity_id)

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._source_entity_id],
                    async_stats_sensor_state_listener,
                )
            )

            if "recorder" in self.hass.config.components:
                self.hass.async_create_task(self._initialize_from_database())

        async_at_start(self.hass, async_stats_sensor_startup)

    def _add_state_to_queue(self, new_state):
        """Add the state to the queue."""
        self._available = new_state.state != STATE_UNAVAILABLE
        if new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, None):
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
            return

        self._unit_of_measurement = self._derive_unit_of_measurement(new_state)

    def _derive_unit_of_measurement(self, new_state):
        base_unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if not base_unit:
            unit = None
        elif self.is_binary:
            unit = None
        elif self._state_characteristic in (
            STAT_COUNT,
            STAT_MIN_AGE,
            STAT_MAX_AGE,
            STAT_QUANTILES,
        ):
            unit = None
        elif self._state_characteristic in (
            STAT_TOTAL,
            STAT_MEAN,
            STAT_MEDIAN,
            STAT_STANDARD_DEVIATION,
            STAT_MIN_VALUE,
            STAT_MAX_VALUE,
            STAT_CHANGE,
        ):
            unit = base_unit
        elif self._state_characteristic == STAT_VARIANCE:
            unit = base_unit + "²"
        elif self._state_characteristic == STAT_AVERAGE_CHANGE:
            unit = base_unit + "/sample"
        elif self._state_characteristic == STAT_CHANGE_RATE:
            unit = base_unit + "/s"
        return unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state_class(self):
        """Return the state class of this entity."""
        if self._state_characteristic in (
            STAT_MIN_AGE,
            STAT_MAX_AGE,
            STAT_QUANTILES,
        ):
            return None
        return STATE_CLASS_MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.is_binary:
            return self.attr[STAT_COUNT]
        if self._state_characteristic in (
            STAT_MIN_AGE,
            STAT_MAX_AGE,
            STAT_QUANTILES,
        ):
            return self.attr[self._state_characteristic]
        if self._precision == 0:
            with contextlib.suppress(TypeError, ValueError):
                return int(self.attr[self._state_characteristic])
        return self.attr[self._state_characteristic]

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return the availability of the sensor linked to the source sensor."""
        return self._available

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self.is_binary:
            return None
        return self.attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def _purge_old(self):
        """Remove states which are older than self._samples_max_age."""
        now = dt_util.utcnow()

        _LOGGER.debug(
            "%s: purging records older then %s(%s)",
            self.entity_id,
            dt_util.as_local(now - self._samples_max_age),
            self._samples_max_age,
        )

        while self.ages and (now - self.ages[0]) > self._samples_max_age:
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
        if self.ages and self._samples_max_age:
            # Take the oldest entry from the ages list and add the configured max_age.
            # If executed after purging old states, the result is the next timestamp
            # in the future when the oldest state will expire.
            return self.ages[0] + self._samples_max_age
        return None

    def _update_characteristics(self):
        """Calculate and update the various statistical characteristics."""
        states_count = len(self.states)
        self.attr[STAT_COUNT] = states_count

        if self.is_binary:
            return

        if states_count >= 2:
            self.attr[STAT_STANDARD_DEVIATION] = round(
                statistics.stdev(self.states), self._precision
            )
            self.attr[STAT_VARIANCE] = round(
                statistics.variance(self.states), self._precision
            )
        else:
            self.attr[STAT_STANDARD_DEVIATION] = STATE_UNKNOWN
            self.attr[STAT_VARIANCE] = STATE_UNKNOWN

        if states_count > self._quantile_intervals:
            self.attr[STAT_QUANTILES] = [
                round(quantile, self._precision)
                for quantile in statistics.quantiles(
                    self.states,
                    n=self._quantile_intervals,
                    method=self._quantile_method,
                )
            ]
        else:
            self.attr[STAT_QUANTILES] = STATE_UNKNOWN

        if states_count == 0:
            self.attr[STAT_MEAN] = STATE_UNKNOWN
            self.attr[STAT_MEDIAN] = STATE_UNKNOWN
            self.attr[STAT_TOTAL] = STATE_UNKNOWN
            self.attr[STAT_MIN_VALUE] = self.attr[STAT_MAX_VALUE] = STATE_UNKNOWN
            self.attr[STAT_MIN_AGE] = self.attr[STAT_MAX_AGE] = STATE_UNKNOWN
            self.attr[STAT_CHANGE] = self.attr[STAT_AVERAGE_CHANGE] = STATE_UNKNOWN
            self.attr[STAT_CHANGE_RATE] = STATE_UNKNOWN
            return

        self.attr[STAT_MEAN] = round(statistics.mean(self.states), self._precision)
        self.attr[STAT_MEDIAN] = round(statistics.median(self.states), self._precision)

        self.attr[STAT_TOTAL] = round(sum(self.states), self._precision)
        self.attr[STAT_MIN_VALUE] = round(min(self.states), self._precision)
        self.attr[STAT_MAX_VALUE] = round(max(self.states), self._precision)

        self.attr[STAT_MIN_AGE] = self.ages[0]
        self.attr[STAT_MAX_AGE] = self.ages[-1]

        self.attr[STAT_CHANGE] = self.states[-1] - self.states[0]

        self.attr[STAT_AVERAGE_CHANGE] = self.attr[STAT_CHANGE]
        self.attr[STAT_CHANGE_RATE] = 0
        if states_count > 1:
            self.attr[STAT_AVERAGE_CHANGE] /= len(self.states) - 1

            time_diff = (
                self.attr[STAT_MAX_AGE] - self.attr[STAT_MIN_AGE]
            ).total_seconds()
            if time_diff > 0:
                self.attr[STAT_CHANGE_RATE] = self.attr[STAT_CHANGE] / time_diff
        self.attr[STAT_CHANGE] = round(self.attr[STAT_CHANGE], self._precision)
        self.attr[STAT_AVERAGE_CHANGE] = round(
            self.attr[STAT_AVERAGE_CHANGE], self._precision
        )
        self.attr[STAT_CHANGE_RATE] = round(
            self.attr[STAT_CHANGE_RATE], self._precision
        )

    async def async_update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("%s: updating statistics", self.entity_id)
        if self._samples_max_age is not None:
            self._purge_old()

        self._update_characteristics()

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

    async def _initialize_from_database(self):
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
                States.entity_id == self._source_entity_id.lower()
            )

            if self._samples_max_age is not None:
                records_older_then = dt_util.utcnow() - self._samples_max_age
                _LOGGER.debug(
                    "%s: retrieve records not older then %s",
                    self.entity_id,
                    records_older_then,
                )
                query = query.filter(States.last_updated >= records_older_then)
            else:
                _LOGGER.debug("%s: retrieving all records", self.entity_id)

            query = query.order_by(States.last_updated.desc()).limit(
                self._samples_max_buffer_size
            )
            states = execute(query, to_native=True, validate_entity_ids=False)

        for state in reversed(states):
            self._add_state_to_queue(state)

        self.async_schedule_update_ha_state(True)

        _LOGGER.debug("%s: initializing from database completed", self.entity_id)
