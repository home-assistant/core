"""
Transport NSW (AU) sensor to query next leave event for a specified stop.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.transport_nsw/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_API_KEY, ATTR_ATTRIBUTION)

REQUIREMENTS = ['PyTransportNSW==0.0.8']

_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = 'stop_id'
ATTR_ROUTE = 'route'
ATTR_DUE_IN = 'due'
ATTR_DELAY = 'delay'
ATTR_REAL_TIME = 'real_time'

CONF_ATTRIBUTION = "Data provided by Transport NSW"
CONF_STOP_ID = 'stop_id'
CONF_ROUTE = 'route'

DEFAULT_NAME = "Next Bus"
ICON = "mdi:bus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ROUTE, default=""): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Transport NSW sensor."""
    stop_id = config[CONF_STOP_ID]
    api_key = config[CONF_API_KEY]
    route = config.get(CONF_ROUTE)
    name = config.get(CONF_NAME)

    data = PublicTransportData(stop_id, route, api_key)
    add_entities([TransportNSWSensor(data, stop_id, name)], True)


class TransportNSWSensor(Entity):
    """Implementation of an Transport NSW sensor."""

    def __init__(self, data, stop_id, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop_id = stop_id
        self._times = self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._times is not None:
            return {
                ATTR_DUE_IN: self._times[ATTR_DUE_IN],
                ATTR_STOP_ID: self._stop_id,
                ATTR_ROUTE: self._times[ATTR_ROUTE],
                ATTR_DELAY: self._times[ATTR_DELAY],
                ATTR_REAL_TIME: self._times[ATTR_REAL_TIME],
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION
            }

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'min'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from Transport NSW and update the states."""
        self.data.update()
        self._times = self.data.info
        self._state = self._times[ATTR_DUE_IN]


class PublicTransportData:
    """The Class for handling the data retrieval."""

    def __init__(self, stop_id, route, api_key):
        """Initialize the data object."""
        import TransportNSW
        self._stop_id = stop_id
        self._route = route
        self._api_key = api_key
        self.info = {ATTR_ROUTE: self._route,
                     ATTR_DUE_IN: 'n/a',
                     ATTR_DELAY: 'n/a',
                     ATTR_REAL_TIME: 'n/a'}
        self.tnsw = TransportNSW.TransportNSW()

    def update(self):
        """Get the next leave time."""
        _data = self.tnsw.get_departures(self._stop_id,
                                         self._route,
                                         self._api_key)
        self.info = {ATTR_ROUTE: _data['route'],
                     ATTR_DUE_IN: _data['due'],
                     ATTR_DELAY: _data['delay'],
                     ATTR_REAL_TIME: _data['real_time']}
