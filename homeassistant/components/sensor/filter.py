"""
Support for filtering for sensor values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.filter/
"""
import asyncio
import logging
import inspect
import statistics
from collections import deque

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
from homeassistant.util.decorator import Registry

_LOGGER = logging.getLogger(__name__)

ATTR_PRE_FILTER = 'pre_filter_state'

CONF_FILTER_OPTIONS = 'options'
CONF_FILTER_NAME = 'filter'
CONF_WINDOW_SIZE = 'window_size'

DEFAULT_NAME_TEMPLATE = "{} filter {}"
ICON = 'mdi: chart-line-variant'

DEFAULT_WINDOW_SIZE = 5
FILTER_LOWPASS = 'lowpass'
FILTER_OUTLIER = 'outlier'

FILTERS = Registry()


@FILTERS.register(FILTER_OUTLIER)
def _outlier(new_state, stats, states, **kwargs):
    """BASIC outlier filter.

    Determines if new state in a band around the median

    Args:
        new_state (float): new value to the series
        stats (dict): used to feedback stats on the filter
        states (deque): previous data series
        radius (float): band radius

    Returns:
        the original new_state case not an outlier
        the median of the window case it's an outlier

    """
    radius = kwargs.pop('radius', 5)
    erasures = stats.get('erasures', 0)

    if (len(states) > 1 and
            abs(new_state - statistics.median(states)) >
            radius):

        stats['erasures'] = erasures+1
        Filter.logger.warning("Outlier in %s: %s",
                              Filter.sensor_name, float(new_state))
        return states[-1]
    return new_state


@FILTERS.register(FILTER_LOWPASS)
def _lowpass(new_state, stats, states, **kwargs):
    """BASIC Low Pass Filter.

    Args:
        new_state (float): new value to the series
        stats (dict): used to feedback stats on the filter
        states (deque): previous data series
        time_constant (int): time constant.

    Returns:
        a new state value that has been smoothed by filter

    """
    time_constant = kwargs.pop('time_constant', 4)
    precision = kwargs.pop('precision', None)

    if len(kwargs) != 0:
        Filter.logger.error("unrecognized params passed in: %s", kwargs)

    try:
        new_weight = 1.0 / time_constant
        prev_weight = 1.0 - new_weight
        filtered = prev_weight * states[-1] + new_weight * new_state
    except IndexError:
        # if we don't have enough states to run the filter
        # just accept the new value
        filtered = new_state

    if precision is None:
        return filtered
    else:
        return round(filtered, precision)


# ALL filter arguments must be OPTIONAL
FILTER_SCHEMA = vol.Schema({
    vol.Optional('time_constant'): vol.Coerce(int),
    vol.Optional('radius'): vol.Coerce(float)
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_FILTER_NAME):
        vol.In(list(FILTERS)),
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Optional(CONF_WINDOW_SIZE): vol.Coerce(int),
    vol.Optional(CONF_FILTER_OPTIONS): FILTER_SCHEMA,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Filter sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    filter_name = config.get(CONF_FILTER_NAME)
    wsize = config.get(CONF_WINDOW_SIZE)
    name = config.get(CONF_NAME)
    if name is None:
        name = DEFAULT_NAME_TEMPLATE.format(entity_id, filter_name)

    async_add_devices([
        FilterSensor(hass, name, entity_id, filter_name, wsize,
                     config.get(CONF_FILTER_OPTIONS, dict()))
        ], True)


class FilterSensor(Entity):
    """Representation of a Filter sensor."""

    def __init__(self, hass, name, entity_id, filter_name, wsize, filter_args):
        """Initialize the Filter sensor."""
        self._name = name
        self._filter_name = filter_name
        self._unit_of_measurement = None
        self._pre_filter_state = self._state = None

        self._filterdata = self.filterdata_factory(filter_name, wsize,
                                                   **filter_args)(self._name)

        @callback
        # pylint: disable=invalid-name
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT)

            if new_state.state is None or new_state.state is STATE_UNKNOWN:
                return

            try:
                self._pre_filter_state = new_state.state
                self._filterdata.update(self._pre_filter_state)
            except ValueError:
                _LOGGER.warning("Could not convert <%s> into a number",
                                self._pre_filter_state)
                return

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_stats_sensor_state_listener)

    @property
    def available(self):
        """Return True if there is data to filter."""
        return self._pre_filter_state is not None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._filterdata.data

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_PRE_FILTER: self._pre_filter_state,
            ATTR_UNIT_OF_MEASUREMENT: self._unit_of_measurement
        }
        state_attr.update(self._filterdata.statistics)

        return state_attr

    def filterdata_factory(self, filter_function, window_size, **kwargs):
        """Factory to create filters with user provided arguments."""
        class FilterData(object):
            """Support dynamic decorator arguments."""

            def __init__(self, sensor_name):
                """Initialize adaptor."""
                self._data = None
                self.filter_stats = {}
                self.entity_id = sensor_name

            @property
            @Filter(filter_function, window_size, **kwargs)
            def data(self):
                """Filtered data."""
                return self._data

            @property
            def statistics(self):
                """Get statistics on filter execution."""
                return self.filter_stats

            def update(self, new_data):
                """Update raw data."""
                self._data = float(new_data)

        return FilterData


class Filter(object):
    """Filter decorator."""

    logger = None
    sensor_name = None

    def __init__(self, filter_algorithm, window_size=DEFAULT_WINDOW_SIZE,
                 **kwargs):
        """Decorator constructor, selects algorithm and configures window.

        Args:
            filter_algorithm (int): must be one of the defined filters
            window_size (int): size of the sliding window that holds previous
                                values
            kwargs (dict): arguments to be passed to the specific filter

        """
        module_name = inspect.getmodule(inspect.stack()[1][0]).__name__
        Filter.logger = logging.getLogger(module_name)
        Filter.logger.debug("Filter %s(%s) on %s", filter_algorithm, kwargs,
                            module_name)
        self.filter_args = kwargs
        self.filter_stats = {'filter': filter_algorithm}
        self.states = deque(maxlen=window_size)

        if filter_algorithm in FILTERS:
            self.filter = FILTERS[filter_algorithm]
        else:
            self.logger.error("Unknown filter <%s>", filter_algorithm)
            return

    def __call__(self, func):
        """Decorate function as filter."""
        def func_wrapper(sensor_object):
            """Wrap for the original state() function."""
            Filter.sensor_name = sensor_object.entity_id
            new_state = func(sensor_object)
            try:
                filtered_state = self.filter(new_state=float(new_state),
                                             stats=self.filter_stats,
                                             states=self.states,
                                             **self.filter_args)
            except TypeError:
                return None

            self.states.append(filtered_state)

            # filter_stats makes available few statistics to the sensor
            sensor_object.filter_stats = self.filter_stats

            Filter.logger.debug("%s(%s) -> %s", self.filter_stats['filter'],
                                new_state, filtered_state)
            return filtered_state

        return func_wrapper
