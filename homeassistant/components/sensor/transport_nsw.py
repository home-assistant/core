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
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION)

REQUIREMENTS = ['TransportNSW==0.0.2']

_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = 'stopid'
ATTR_ROUTE = 'route'
ATTR_DUE_IN = 'due'
ATTR_DELAY = 'delay'
ATTR_REALTIME = 'realtime'

CONF_ATTRIBUTION = "Data provided by Transport NSW"
CONF_STOP_ID = 'stopid'
CONF_ROUTE = 'route'
CONF_APIKEY = 'apikey'

DEFAULT_NAME = "Next Bus"
ICON = "mdi:bus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Required(CONF_APIKEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ROUTE, default=""): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Transport NSW sensor."""
    name = config.get(CONF_NAME)
    stopid = config.get(CONF_STOP_ID)
    route = config.get(CONF_ROUTE)
    apikey = config.get(CONF_APIKEY)

    data = PublicTransportData(stopid, route, apikey)
    add_devices([TransportNSWSensor(data, stopid, route, name)], True)


class TransportNSWSensor(Entity):
    """Implementation of an Transport NSW sensor."""

    def __init__(self, data, stopid, route, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stopid = stopid
        self._route = route
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
                ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
                ATTR_STOP_ID: self._stopid,
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_DELAY: self._times[0][ATTR_DELAY],
                ATTR_REALTIME: self._times[0][ATTR_REALTIME],
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
        try:
            self._state = self._times[0][ATTR_DUE_IN]
        except TypeError:
            pass


class PublicTransportData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, stopid, route, apikey):
        """Initialize the data object."""
        from TransportNSW import TransportNSW
        self._stopid = stopid
        self._route = route
        self._apikey = apikey
        self.info = [{ATTR_ROUTE: self._route,
                      ATTR_DUE_IN: 'n/a',
                      ATTR_DELAY: 'n/a',
                      ATTR_REALTIME: 'n/a'}]
        self.tnsw = TransportNSW.TransportNSW()

    def update(self):
        """Get the next leave time"""
        _data = self.tnsw.get_departures(self._stopid,
                                         self._route,
                                         self._apikey)
        self.info = [{ATTR_ROUTE: _data[0]['route'],
                      ATTR_DUE_IN: _data[0]['due'],
                      ATTR_DELAY: _data[0]['delay'],
                      ATTR_REALTIME: _data[0]['realtime']}]
        return
