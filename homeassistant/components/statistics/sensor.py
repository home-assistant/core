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

STAT_AGE_COVERAGE_RATIO = "age_coverage_ratio"
STAT_BUFFER_USAGE_RATIO = "buffer_usage_ratio"
STAT_SOURCE_VALUE_VALID = "source_value_valid"

STAT_AVERAGE_LINEAR = "average_linear"
STAT_AVERAGE_STEP = "average_step"
STAT_AVERAGE_TIMELESS = "average_timeless"
STAT_CHANGE = "change"
STAT_CHANGE_SAMPLE = "change_sample"
STAT_CHANGE_SECOND = "change_second"
STAT_COUNT = "count"
STAT_DATETIME_NEWEST = "datetime_newest"
STAT_DATETIME_OLDEST = "datetime_oldest"
STAT_DISTANCE_95P = "distance_95_percent_of_values"
STAT_DISTANCE_99P = "distance_99_percent_of_values"
STAT_DISTANCE_ABSOLUTE = "distance_absolute"
STAT_MEAN = "mean"
STAT_MEDIAN = "median"
STAT_NOISINESS = "noisiness"
STAT_QUANTILES = "quantiles"
STAT_STANDARD_DEVIATION = "standard_deviation"
STAT_TOTAL = "total"
STAT_VALUE_MAX = "value_max"
STAT_VALUE_MIN = "value_min"
STAT_VARIANCE = "variance"

STATS_NOT_A_NUMBER = (
    STAT_DATETIME_OLDEST,
    STAT_DATETIME_NEWEST,
    STAT_QUANTILES,
)

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
                STAT_AVERAGE_LINEAR,
                STAT_AVERAGE_STEP,
                STAT_AVERAGE_TIMELESS,
                STAT_CHANGE_SAMPLE,
                STAT_CHANGE_SECOND,
                STAT_CHANGE,
                STAT_COUNT,
                STAT_DATETIME_NEWEST,
                STAT_DATETIME_OLDEST,
                STAT_DISTANCE_95P,
                STAT_DISTANCE_99P,
                STAT_DISTANCE_ABSOLUTE,
                STAT_MEAN,
                STAT_MEDIAN,
                STAT_NOISINESS,
                STAT_QUANTILES,
                STAT_STANDARD_DEVIATION,
                STAT_TOTAL,
                STAT_VALUE_MAX,
                STAT_VALUE_MIN,
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
        self._state_characteristic = state_characteristic
        self._samples_max_buffer_size = samples_max_buffer_size
        self._samples_max_age = samples_max_age
        self._precision = precision
        self._quantile_intervals = quantile_intervals
        self._quantile_method = quantile_method
        self._value = None
        self._unit_of_measurement = None
        self._available = False
        self.states = deque(maxlen=self._samples_max_buffer_size)
        self.ages = deque(maxlen=self._samples_max_buffer_size)
        self.attributes = {
            STAT_AGE_COVERAGE_RATIO: STATE_UNKNOWN,
            STAT_BUFFER_USAGE_RATIO: STATE_UNKNOWN,
            STAT_SOURCE_VALUE_VALID: STATE_UNKNOWN,
        }
        self._state_characteristic_fn = getattr(
            self, f"_stat_{self._state_characteristic}"
        )

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
        if new_state.state == STATE_UNAVAILABLE:
            self.attributes[STAT_SOURCE_VALUE_VALID] = None
            return
        if new_state.state in (STATE_UNKNOWN, None):
            self.attributes[STAT_SOURCE_VALUE_VALID] = False
            return

        try:
            if self.is_binary:
                self.states.append(new_state.state)
            else:
                self.states.append(float(new_state.state))
            self.ages.append(new_state.last_updated)
            self.attributes[STAT_SOURCE_VALUE_VALID] = True
        except ValueError:
            self.attributes[STAT_SOURCE_VALUE_VALID] = False
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
            STAT_AVERAGE_LINEAR,
            STAT_AVERAGE_STEP,
            STAT_AVERAGE_TIMELESS,
            STAT_CHANGE,
            STAT_DISTANCE_95P,
            STAT_DISTANCE_99P,
            STAT_DISTANCE_ABSOLUTE,
            STAT_MEAN,
            STAT_MEDIAN,
            STAT_NOISINESS,
            STAT_STANDARD_DEVIATION,
            STAT_TOTAL,
            STAT_VALUE_MAX,
            STAT_VALUE_MIN,
        ):
            unit = base_unit
        elif self._state_characteristic in (
            STAT_COUNT,
            STAT_DATETIME_NEWEST,
            STAT_DATETIME_OLDEST,
            STAT_QUANTILES,
        ):
            unit = None
        elif self._state_characteristic == STAT_VARIANCE:
            unit = base_unit + "²"
        elif self._state_characteristic == STAT_CHANGE_SAMPLE:
            unit = base_unit + "/sample"
        elif self._state_characteristic == STAT_CHANGE_SECOND:
            unit = base_unit + "/s"
        return unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state_class(self):
        """Return the state class of this entity."""
        if self.is_binary:
            return STATE_CLASS_MEASUREMENT
        if self._state_characteristic in STATS_NOT_A_NUMBER:
            return None
        return STATE_CLASS_MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._value

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
        extra_attr = {}
        if self._samples_max_age is not None:
            extra_attr = {
                STAT_AGE_COVERAGE_RATIO: self.attributes[STAT_AGE_COVERAGE_RATIO]
            }
        return {
            **extra_attr,
            STAT_BUFFER_USAGE_RATIO: self.attributes[STAT_BUFFER_USAGE_RATIO],
            STAT_SOURCE_VALUE_VALID: self.attributes[STAT_SOURCE_VALUE_VALID],
        }

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

    async def async_update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("%s: updating statistics", self.entity_id)
        if self._samples_max_age is not None:
            self._purge_old()

        self._update_attributes()
        self._update_value()

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

    def _update_attributes(self):
        """Calculate and update the various attributes."""
        self.attributes[STAT_BUFFER_USAGE_RATIO] = round(
            len(self.states) / self._samples_max_buffer_size, 2
        )

        if len(self.states) >= 1 and self._samples_max_age is not None:
            self.attributes[STAT_AGE_COVERAGE_RATIO] = round(
                (self.ages[-1] - self.ages[0]).total_seconds()
                / self._samples_max_age.total_seconds(),
                2,
            )
        else:
            self.attributes[STAT_AGE_COVERAGE_RATIO] = STATE_UNKNOWN

    def _update_value(self):
        """Front to call the right statistical characteristics functions.

        One of the _stat_*() functions is represented by self._state_characteristic_fn().
        """

        if self.is_binary:
            self._value = len(self.states)
            return

        value = self._state_characteristic_fn()

        if self._state_characteristic not in STATS_NOT_A_NUMBER:
            with contextlib.suppress(TypeError):
                value = round(value, self._precision)
                if self._precision == 0:
                    value = int(value)
        self._value = value

    def _stat_average_linear(self):
        if len(self.states) >= 2:
            area = 0
            for i in range(1, len(self.states)):
                area += (
                    0.5
                    * (self.states[i] + self.states[i - 1])
                    * (self.ages[i] - self.ages[i - 1]).total_seconds()
                )
            age_range_seconds = (self.ages[-1] - self.ages[0]).total_seconds()
            return area / age_range_seconds
        return STATE_UNKNOWN

    def _stat_average_step(self):
        if len(self.states) >= 2:
            area = 0
            for i in range(1, len(self.states)):
                area += (
                    self.states[i - 1]
                    * (self.ages[i] - self.ages[i - 1]).total_seconds()
                )
            age_range_seconds = (self.ages[-1] - self.ages[0]).total_seconds()
            return area / age_range_seconds
        return STATE_UNKNOWN

    def _stat_average_timeless(self):
        return self._stat_mean()

    def _stat_change(self):
        if len(self.states) > 0:
            return self.states[-1] - self.states[0]
        return STATE_UNKNOWN

    def _stat_change_sample(self):
        if len(self.states) > 1:
            return (self.states[-1] - self.states[0]) / (len(self.states) - 1)
        return STATE_UNKNOWN

    def _stat_change_second(self):
        if len(self.states) > 1:
            age_range_seconds = (self.ages[-1] - self.ages[0]).total_seconds()
            if age_range_seconds > 0:
                return (self.states[-1] - self.states[0]) / age_range_seconds
        return STATE_UNKNOWN

    def _stat_count(self):
        return len(self.states)

    def _stat_datetime_newest(self):
        if len(self.states) > 0:
            return self.ages[-1]
        return STATE_UNKNOWN

    def _stat_datetime_oldest(self):
        if len(self.states) > 0:
            return self.ages[0]
        return STATE_UNKNOWN

    def _stat_distance_95_percent_of_values(self):
        if len(self.states) >= 2:
            return 2 * 1.96 * self._stat_standard_deviation()
        return STATE_UNKNOWN

    def _stat_distance_99_percent_of_values(self):
        if len(self.states) >= 2:
            return 2 * 2.58 * self._stat_standard_deviation()
        return STATE_UNKNOWN

    def _stat_distance_absolute(self):
        if len(self.states) > 0:
            return max(self.states) - min(self.states)
        return STATE_UNKNOWN

    def _stat_mean(self):
        if len(self.states) > 0:
            return statistics.mean(self.states)
        return STATE_UNKNOWN

    def _stat_median(self):
        if len(self.states) > 0:
            return statistics.median(self.states)
        return STATE_UNKNOWN

    def _stat_noisiness(self):
        if len(self.states) >= 2:
            diff_sum = sum(
                abs(j - i) for i, j in zip(list(self.states), list(self.states)[1:])
            )
            return diff_sum / (len(self.states) - 1)
        return STATE_UNKNOWN

    def _stat_quantiles(self):
        if len(self.states) > self._quantile_intervals:
            return [
                round(quantile, self._precision)
                for quantile in statistics.quantiles(
                    self.states,
                    n=self._quantile_intervals,
                    method=self._quantile_method,
                )
            ]
        return STATE_UNKNOWN

    def _stat_standard_deviation(self):
        if len(self.states) >= 2:
            return statistics.stdev(self.states)
        return STATE_UNKNOWN

    def _stat_total(self):
        if len(self.states) > 0:
            return sum(self.states)
        return STATE_UNKNOWN

    def _stat_value_max(self):
        if len(self.states) > 0:
            return max(self.states)
        return STATE_UNKNOWN

    def _stat_value_min(self):
        if len(self.states) > 0:
            return min(self.states)
        return STATE_UNKNOWN

    def _stat_variance(self):
        if len(self.states) >= 2:
            return statistics.variance(self.states)
        return STATE_UNKNOWN
