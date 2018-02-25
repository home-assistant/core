"""
Allows the creation of a sensor that filters state property.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.filter/
"""
import asyncio
import logging
import statistics
from collections import deque

import voluptuous as vol

from homeassistant.util import slugify
from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, ATTR_ENTITY_ID)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

FILTER_NAME_LOWPASS = 'lowpass'
FILTER_NAME_OUTLIER = 'outlier'

CONF_FILTERS = 'filters'
CONF_FILTER_NAME = 'filter'
CONF_FILTER_WINDOW_SIZE = 'window_size'
CONF_FILTER_PRECISION = 'precision'
CONF_FILTER_RADIUS = 'radius'
CONF_FILTER_TIME_CONSTANT = 'time_constant'

DEFAULT_FILTER_RADIUS = 2.0
DEFAULT_FILTER_TIME_CONSTANT = 10

NAME_TEMPLATE = "{} filter"
ICON = 'mdi: chart-line-variant'

FILTER_SCHEMA = vol.Schema({
    vol.Optional(CONF_FILTER_WINDOW_SIZE): vol.Coerce(int),
    vol.Optional(CONF_FILTER_PRECISION): vol.Coerce(int),
})

FILTER_OUTLIER_SCHEMA = FILTER_SCHEMA.extend({
    vol.Required(CONF_FILTER_NAME): FILTER_NAME_OUTLIER,
    vol.Optional(CONF_FILTER_RADIUS,
                 default=DEFAULT_FILTER_RADIUS): vol.Coerce(float),
})

FILTER_LOWPASS_SCHEMA = FILTER_SCHEMA.extend({
    vol.Required(CONF_FILTER_NAME): FILTER_NAME_LOWPASS,
    vol.Optional(CONF_FILTER_TIME_CONSTANT,
                 default=DEFAULT_FILTER_TIME_CONSTANT): vol.Coerce(int),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_FILTERS): vol.All(cv.ensure_list,
                                        [vol.Any(FILTER_OUTLIER_SCHEMA,
                                                 FILTER_LOWPASS_SCHEMA)])
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the template sensors."""
    sensors = []

    name = config.get(CONF_NAME)
    entity_id = config.get(CONF_ENTITY_ID)
    filters = []

    for _filter in config[CONF_FILTERS]:
        window_size = _filter.get(CONF_FILTER_WINDOW_SIZE)
        precision = _filter.get(CONF_FILTER_PRECISION)

        if _filter[CONF_FILTER_NAME] == FILTER_NAME_OUTLIER:
            radius = _filter.get(CONF_FILTER_RADIUS)
            filters.append(OutlierFilter(window_size=window_size,
                                         precision=precision,
                                         radius=radius))
        elif _filter[CONF_FILTER_NAME] == FILTER_NAME_LOWPASS:
            time_constant = _filter.get(CONF_FILTER_TIME_CONSTANT)
            filters.append(LowPassFilter(window_size=window_size,
                                         precision=precision,
                                         time_constant=time_constant))

    sensors.append(SensorFilter(name, entity_id, filters))

    async_add_devices(sensors)


class SensorFilter(Entity):
    """Representation of a Filter Sensor."""

    def __init__(self, name, entity_id, filters):
        """Initialize the sensor."""
        self._name = name
        self._entity = entity_id
        self._unit_of_measurement = None
        self._state = None
        self._filters = filters

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def filter_sensor_state_listener(entity, old_state, new_state):
            """Handle device state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT)

            self._state = new_state.state
            for filt in self._filters:
                try:
                    filtered_state = filt.filter_state(self._state)
                    _LOGGER.debug("%s(%s) -> %s", filt.name, self._state,
                                  filtered_state)
                    self._state = filtered_state
                    filt.states.append(filtered_state)
                except ValueError:
                    _LOGGER.warning("Could not convert state: %s to number",
                                    self._state)

            self.async_schedule_update_ha_state(True)

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
        return ICON

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
        for filt in self._filters:
            state_attr.update({
                slugify("{} stats".format(filt.name)): filt.stats
            })

        return state_attr


class Filter(object):
    """Filter skeleton.

    Args:
        window_size (int): size of the sliding window that holds previous
                                values
    """

    def __init__(self, name, window_size=1, precision=None):
        """Initialize common attributes."""
        self.states = deque(maxlen=window_size)
        self.precision = precision
        self._stats = {}
        self._name = name

    @property
    def name(self):
        """Return filter name."""
        return self._name

    @property
    def stats(self):
        """Return statistics of the filter."""
        return self._stats

    def _filter_state(self, new_state):
        """Implement filter."""
        raise NotImplementedError()

    def filter_state(self, new_state):
        """Implement a common interface for filters."""
        filtered = self._filter_state(new_state)
        if self.precision is None:
            return filtered
        return round(filtered, self.precision)


class OutlierFilter(Filter):
    """BASIC outlier filter.

    Determines if new state is in a band around the median.

    Args:
        radius (float): band radius
        window_size (int): see Filter()
    """

    def __init__(self, window_size, precision, radius):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_OUTLIER, window_size, precision)
        self._radius = radius

    def _filter_state(self, new_state):
        """Implement the outlier filter."""
        new_state = float(new_state)
        if (len(self.states) > 1 and
                abs(new_state - statistics.median(self.states))
                > self._radius):

            erasures = self._stats.get('erasures', 0)
            self._stats['erasures'] = erasures+1

            _LOGGER.debug("Outlier in %s: %s", self._name, new_state)
            return self.states[-1]
        return new_state


class LowPassFilter(Filter):
    """BASIC Low Pass Filter.

    Args:
        time_constant (int): time constant.
        window_size (int): see Filter()
    """

    def __init__(self, window_size, precision, time_constant):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_LOWPASS, window_size, precision)
        self._time_constant = time_constant

    def _filter_state(self, new_state):
        """Implement the low pass filter."""
        new_state = float(new_state)

        try:
            new_weight = 1.0 / self._time_constant
            prev_weight = 1.0 - new_weight
            filtered = prev_weight * self.states[-1] + new_weight * new_state
        except IndexError:
            # if we don't have enough states to run the filter
            # just accept the new value
            filtered = new_state

        return filtered
