"""
Support for filtering for sensor values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.filter/
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
from homeassistant.components.recorder.util import session_scope, execute

REQUIREMENTS = ['pyserial-asyncio==0.4']

_LOGGER = logging.getLogger(__name__)

ATTR_COUNT = 'count'
ATTR_FILTER = 'filtered'
ATTR_SAMPLING_SIZE = 'window_size'

CONF_WINDOW_SIZE = 'window_size'

DEFAULT_NAME = 'Filter'
DEFAULT_SIZE = 5
ICON = 'mdi: chart-line-variant '

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_WINDOW_SIZE, default=DEFAULT_SIZE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Statistics sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    window_size = config.get(CONF_WINDOW_SIZE)

    async_add_devices(
        [FilterSensor(hass, entity_id, name, window_size)],
        True)
    return True


class FilterSensor(Entity):
    """Representation of a Filter sensor."""

    def __init__(self, hass, entity_id, name, window_size):
        """Initialize the Statistics sensor."""
        self._hass = hass
        self._entity_id = entity_id
        self._name = '{} {}'.format(name, ATTR_FILTER)
        self._window_size = window_size
        self._unit_of_measurement = None
        self.states = deque(maxlen=self._window_size)

        if 'recorder' in self._hass.config.components:
            # only use the database if it's configured
            hass.async_add_job(self._initialize_from_database)

        @callback
        # pylint: disable=invalid-name
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT)

            self._add_state_to_queue(new_state)

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_stats_sensor_state_listener)

    def _add_state_to_queue(self, new_state):
        """Add a single state to states."""
        try:
            _LOGGER.debug("New value: %s", new_state.state)
            new_state.state = float(new_state.state)

            #Outliers filters:
            self._outlier(new_state.state)

            #Smooth filters:
            self.states.append(self._lowpass(new_state.state))
        except ValueError as e:
            _LOGGER.error("Invalid Value: %s, reason: %s", float(new_state.state), e)

    def _outlier(self, new_state):
        """BASIC outlier filter.
        Where does 10 SD come from?"""
        if len(self.states) > 1 and abs(new_state - statistics.median(self.states)) > 10*statistics.stdev(self.states):
            raise ValueError("Outlier detected")

    def _lowpass(self, new_state, time_constant=4):
        """BASIC Low Pass Filter.
        COULD REPLACE WITH _FILTER THEN DEFINE WHATEVER FILTER WE WANT?"""
        try:
            B = 1.0 / time_constant
            A = 1.0 - B
            filtered = A * self.states[-1] + B * new_state
        except IndexError:
            # if we don't have enough states to run the filter, just accept the new value
            filtered = new_state
        return round(filtered, 2)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if len(self.states):
            return self.states[-1]
        else:
            return STATE_UNKNOWN # I think STATE_UNKNOWN is discouraged

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
        """Return the icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        try:  # require at least two data points
            _LOGGER.debug("<%s> variance %s", self.states[-1], round(statistics.variance(self.states), 2))
        except statistics.StatisticsError as err:
            _LOGGER.error(err)
            self.variance = STATE_UNKNOWN


    @asyncio.coroutine
    def _initialize_from_database(self):
        """Initialize the list of states from the database.

        The query will get the list of states in DESCENDING order so that we
        can limit the result to self._sample_size. Afterwards reverse the
        list so that we get it in the right order again.
        """
        from homeassistant.components.recorder.models import States
        _LOGGER.debug("initializing values for %s from the database",
                      self._entity_id)

        with session_scope(hass=self._hass) as session:
            query = session.query(States)\
                .filter(States.entity_id == self._entity_id.lower())\
                .order_by(States.last_updated.desc())\
                .limit(self._window_size)
            states = execute(query)

        for state in reversed(states):
            self._add_state_to_queue(state)

        _LOGGER.debug("initializing from database completed")
