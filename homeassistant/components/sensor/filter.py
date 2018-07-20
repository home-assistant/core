"""
Allows the creation of a sensor that filters state property.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.filter/
"""
import logging
import statistics
from collections import deque, Counter
from numbers import Number
from functools import partial
from copy import copy
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, ATTR_ENTITY_ID,
    ATTR_ICON, STATE_UNKNOWN, STATE_UNAVAILABLE)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.decorator import Registry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
from homeassistant.components import history
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

FILTER_NAME_RANGE = 'range'
FILTER_NAME_LOWPASS = 'lowpass'
FILTER_NAME_OUTLIER = 'outlier'
FILTER_NAME_THROTTLE = 'throttle'
FILTER_NAME_TIME_SMA = 'time_simple_moving_average'
FILTERS = Registry()

CONF_FILTERS = 'filters'
CONF_FILTER_NAME = 'filter'
CONF_FILTER_WINDOW_SIZE = 'window_size'
CONF_FILTER_PRECISION = 'precision'
CONF_FILTER_RADIUS = 'radius'
CONF_FILTER_TIME_CONSTANT = 'time_constant'
CONF_FILTER_LOWER_BOUND = 'lower_bound'
CONF_FILTER_UPPER_BOUND = 'upper_bound'
CONF_TIME_SMA_TYPE = 'type'

TIME_SMA_LAST = 'last'

WINDOW_SIZE_UNIT_NUMBER_EVENTS = 1
WINDOW_SIZE_UNIT_TIME = 2

DEFAULT_WINDOW_SIZE = 1
DEFAULT_PRECISION = 2
DEFAULT_FILTER_RADIUS = 2.0
DEFAULT_FILTER_TIME_CONSTANT = 10

NAME_TEMPLATE = "{} filter"
ICON = 'mdi:chart-line-variant'

FILTER_SCHEMA = vol.Schema({
    vol.Optional(CONF_FILTER_PRECISION,
                 default=DEFAULT_PRECISION): vol.Coerce(int),
})

# pylint: disable=redefined-builtin
FILTER_OUTLIER_SCHEMA = FILTER_SCHEMA.extend({
    vol.Required(CONF_FILTER_NAME): FILTER_NAME_OUTLIER,
    vol.Optional(CONF_FILTER_WINDOW_SIZE,
                 default=DEFAULT_WINDOW_SIZE): vol.Coerce(int),
    vol.Optional(CONF_FILTER_RADIUS,
                 default=DEFAULT_FILTER_RADIUS): vol.Coerce(float),
})

FILTER_LOWPASS_SCHEMA = FILTER_SCHEMA.extend({
    vol.Required(CONF_FILTER_NAME): FILTER_NAME_LOWPASS,
    vol.Optional(CONF_FILTER_WINDOW_SIZE,
                 default=DEFAULT_WINDOW_SIZE): vol.Coerce(int),
    vol.Optional(CONF_FILTER_TIME_CONSTANT,
                 default=DEFAULT_FILTER_TIME_CONSTANT): vol.Coerce(int),
})

FILTER_RANGE_SCHEMA = FILTER_SCHEMA.extend({
    vol.Required(CONF_FILTER_NAME): FILTER_NAME_RANGE,
    vol.Optional(CONF_FILTER_LOWER_BOUND): vol.Coerce(float),
    vol.Optional(CONF_FILTER_UPPER_BOUND): vol.Coerce(float),
})

FILTER_TIME_SMA_SCHEMA = FILTER_SCHEMA.extend({
    vol.Required(CONF_FILTER_NAME): FILTER_NAME_TIME_SMA,
    vol.Optional(CONF_TIME_SMA_TYPE,
                 default=TIME_SMA_LAST): vol.In(
                     [TIME_SMA_LAST]),

    vol.Required(CONF_FILTER_WINDOW_SIZE): vol.All(cv.time_period,
                                                   cv.positive_timedelta)
})

FILTER_THROTTLE_SCHEMA = FILTER_SCHEMA.extend({
    vol.Required(CONF_FILTER_NAME): FILTER_NAME_THROTTLE,
    vol.Optional(CONF_FILTER_WINDOW_SIZE,
                 default=DEFAULT_WINDOW_SIZE): vol.Coerce(int),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_FILTERS): vol.All(cv.ensure_list,
                                        [vol.Any(FILTER_OUTLIER_SCHEMA,
                                                 FILTER_LOWPASS_SCHEMA,
                                                 FILTER_TIME_SMA_SCHEMA,
                                                 FILTER_THROTTLE_SCHEMA,
                                                 FILTER_RANGE_SCHEMA)])
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the template sensors."""
    name = config.get(CONF_NAME)
    entity_id = config.get(CONF_ENTITY_ID)

    filters = [FILTERS[_filter.pop(CONF_FILTER_NAME)](
        entity=entity_id, **_filter)
               for _filter in config[CONF_FILTERS]]

    async_add_devices([SensorFilter(name, entity_id, filters)])


class SensorFilter(Entity):
    """Representation of a Filter Sensor."""

    def __init__(self, name, entity_id, filters):
        """Initialize the sensor."""
        self._name = name
        self._entity = entity_id
        self._unit_of_measurement = None
        self._state = None
        self._filters = filters
        self._icon = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def filter_sensor_state_listener(entity, old_state, new_state,
                                         update_ha=True):
            """Handle device state changes."""
            if new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                return

            temp_state = new_state

            try:
                for filt in self._filters:
                    filtered_state = filt.filter_state(copy(temp_state))
                    _LOGGER.debug("%s(%s=%s) -> %s", filt.name,
                                  self._entity,
                                  temp_state.state,
                                  "skip" if filt.skip_processing else
                                  filtered_state.state)
                    if filt.skip_processing:
                        return
                    temp_state = filtered_state
            except ValueError:
                _LOGGER.error("Could not convert state: %s to number",
                              self._state)
                return

            self._state = temp_state.state

            if self._icon is None:
                self._icon = new_state.attributes.get(
                    ATTR_ICON, ICON)

            if self._unit_of_measurement is None:
                self._unit_of_measurement = new_state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT)

            if update_ha:
                self.async_schedule_update_ha_state()

        if 'recorder' in self.hass.config.components:
            history_list = []
            largest_window_items = 0
            largest_window_time = timedelta(0)

            # Determine the largest window_size by type
            for filt in self._filters:
                if filt.window_unit == WINDOW_SIZE_UNIT_NUMBER_EVENTS\
                        and largest_window_items < filt.window_size:
                    largest_window_items = filt.window_size
                elif filt.window_unit == WINDOW_SIZE_UNIT_TIME\
                        and largest_window_time < filt.window_size:
                    largest_window_time = filt.window_size

            # Retrieve the largest window_size of each type
            if largest_window_items > 0:
                filter_history = await self.hass.async_add_job(partial(
                    history.get_last_state_changes, self.hass,
                    largest_window_items, entity_id=self._entity))
                history_list.extend(
                    [state for state in filter_history[self._entity]])
            if largest_window_time > timedelta(seconds=0):
                start = dt_util.utcnow() - largest_window_time
                filter_history = await self.hass.async_add_job(partial(
                    history.state_changes_during_period, self.hass,
                    start, entity_id=self._entity))
                history_list.extend(
                    [state for state in filter_history[self._entity]
                     if state not in history_list])

            # Sort the window states
            history_list = sorted(history_list, key=lambda s: s.last_updated)
            _LOGGER.debug("Loading from history: %s",
                          [(s.state, s.last_updated) for s in history_list])

            # Replay history through the filter chain
            prev_state = None
            for state in history_list:
                filter_sensor_state_listener(
                    self._entity, prev_state, state, False)
                prev_state = state

        async_track_state_change(
            self.hass, self._entity, filter_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_ENTITY_ID: self._entity
        }
        return state_attr


class FilterState:
    """State abstraction for filter usage."""

    def __init__(self, state):
        """Initialize with HA State object."""
        self.timestamp = state.last_updated
        try:
            self.state = float(state.state)
        except ValueError:
            self.state = state.state

    def set_precision(self, precision):
        """Set precision of Number based states."""
        if isinstance(self.state, Number):
            self.state = round(float(self.state), precision)

    def __str__(self):
        """Return state as the string representation of FilterState."""
        return str(self.state)

    def __repr__(self):
        """Return timestamp and state as the representation of FilterState."""
        return "{} : {}".format(self.timestamp, self.state)


class Filter:
    """Filter skeleton.

    Args:
        window_size (int): size of the sliding window that holds previous
                                values
        precision (int): round filtered value to precision value
        entity (string): used for debugging only
    """

    def __init__(self, name, window_size=1, precision=None, entity=None):
        """Initialize common attributes."""
        if isinstance(window_size, int):
            self.states = deque(maxlen=window_size)
            self.window_unit = WINDOW_SIZE_UNIT_NUMBER_EVENTS
        else:
            self.states = deque(maxlen=0)
            self.window_unit = WINDOW_SIZE_UNIT_TIME
        self.precision = precision
        self._name = name
        self._entity = entity
        self._skip_processing = False
        self._window_size = window_size

    @property
    def window_size(self):
        """Return window size."""
        return self._window_size

    @property
    def name(self):
        """Return filter name."""
        return self._name

    @property
    def skip_processing(self):
        """Return wether the current filter_state should be skipped."""
        return self._skip_processing

    def _filter_state(self, new_state):
        """Implement filter."""
        raise NotImplementedError()

    def filter_state(self, new_state):
        """Implement a common interface for filters."""
        filtered = self._filter_state(FilterState(new_state))
        filtered.set_precision(self.precision)
        self.states.append(copy(filtered))
        new_state.state = filtered.state
        return new_state


@FILTERS.register(FILTER_NAME_RANGE)
class RangeFilter(Filter):
    """Range filter.

    Determines if new state is in the range of upper_bound and lower_bound.
    If not inside, lower or upper bound is returned instead.

    Args:
        upper_bound (float): band upper bound
        lower_bound (float): band lower bound
    """

    def __init__(self, entity,
                 lower_bound, upper_bound):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_RANGE, entity=entity)
        self._lower_bound = lower_bound
        self._upper_bound = upper_bound
        self._stats_internal = Counter()

    def _filter_state(self, new_state):
        """Implement the range filter."""
        if self._upper_bound and new_state.state > self._upper_bound:

            self._stats_internal['erasures_up'] += 1

            _LOGGER.debug("Upper outlier nr. %s in %s: %s",
                          self._stats_internal['erasures_up'],
                          self._entity, new_state)
            new_state.state = self._upper_bound

        elif self._lower_bound and new_state.state < self._lower_bound:

            self._stats_internal['erasures_low'] += 1

            _LOGGER.debug("Lower outlier nr. %s in %s: %s",
                          self._stats_internal['erasures_low'],
                          self._entity, new_state)
            new_state.state = self._lower_bound

        return new_state


@FILTERS.register(FILTER_NAME_OUTLIER)
class OutlierFilter(Filter):
    """BASIC outlier filter.

    Determines if new state is in a band around the median.

    Args:
        radius (float): band radius
    """

    def __init__(self, window_size, precision, entity, radius):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_OUTLIER, window_size, precision, entity)
        self._radius = radius
        self._stats_internal = Counter()

    def _filter_state(self, new_state):
        """Implement the outlier filter."""
        if (len(self.states) == self.states.maxlen and
                abs(new_state.state -
                    statistics.median([s.state for s in self.states])) >
                self._radius):

            self._stats_internal['erasures'] += 1

            _LOGGER.debug("Outlier nr. %s in %s: %s",
                          self._stats_internal['erasures'],
                          self._entity, new_state)
            return self.states[-1]
        return new_state


@FILTERS.register(FILTER_NAME_LOWPASS)
class LowPassFilter(Filter):
    """BASIC Low Pass Filter.

    Args:
        time_constant (int): time constant.
    """

    def __init__(self, window_size, precision, entity, time_constant):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_LOWPASS, window_size, precision, entity)
        self._time_constant = time_constant

    def _filter_state(self, new_state):
        """Implement the low pass filter."""
        if not self.states:
            return new_state

        new_weight = 1.0 / self._time_constant
        prev_weight = 1.0 - new_weight
        new_state.state = prev_weight * self.states[-1].state +\
            new_weight * new_state.state

        return new_state


@FILTERS.register(FILTER_NAME_TIME_SMA)
class TimeSMAFilter(Filter):
    """Simple Moving Average (SMA) Filter.

    The window_size is determined by time, and SMA is time weighted.

    Args:
        variant (enum): type of argorithm used to connect discrete values
    """

    def __init__(self, window_size, precision, entity, type):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_TIME_SMA, window_size, precision, entity)
        self._time_window = window_size
        self.last_leak = None
        self.queue = deque()

    def _leak(self, left_boundary):
        """Remove timeouted elements."""
        while self.queue:
            if self.queue[0].timestamp + self._time_window <= left_boundary:
                self.last_leak = self.queue.popleft()
            else:
                return

    def _filter_state(self, new_state):
        """Implement the Simple Moving Average filter."""
        self._leak(new_state.timestamp)
        self.queue.append(copy(new_state))

        moving_sum = 0
        start = new_state.timestamp - self._time_window
        prev_state = self.last_leak or self.queue[0]
        for state in self.queue:
            moving_sum += (state.timestamp-start).total_seconds()\
                          * prev_state.state
            start = state.timestamp
            prev_state = state

        new_state.state = moving_sum / self._time_window.total_seconds()

        return new_state


@FILTERS.register(FILTER_NAME_THROTTLE)
class ThrottleFilter(Filter):
    """Throttle Filter.

    One sample per window.
    """

    def __init__(self, window_size, precision, entity):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_THROTTLE, window_size, precision, entity)

    def _filter_state(self, new_state):
        """Implement the throttle filter."""
        if not self.states or len(self.states) == self.states.maxlen:
            self.states.clear()
            self._skip_processing = False
        else:
            self._skip_processing = True

        return new_state
