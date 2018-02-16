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
from homeassistant.helpers.filter import Filter, FILTER_OUTLIER, FILTER_LOWPASS 
from homeassistant.helpers.event import async_track_state_change
from homeassistant.components.recorder.util import session_scope, execute

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
        self._state = None

        @callback
        # pylint: disable=invalid-name
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT)

            self._state = new_state.state

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_stats_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    @Filter(FILTER_LOWPASS)
    def state(self):
        """Return the state of the sensor."""
        return self._state

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
