"""
Sensor for the Open Sky Network.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.opensky/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS,
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE,
    LENGTH_KILOMETERS, LENGTH_METERS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import distance as util_distance
from homeassistant.util import location as util_location

_LOGGER = logging.getLogger(__name__)

ATTR_CALLSIGN = 'callsign'
ATTR_ON_GROUND = 'on_ground'
ATTR_SENSOR = 'sensor'
ATTR_STATES = 'states'

DOMAIN = 'opensky'

EVENT_OPENSKY_ENTRY = '{}_entry'.format(DOMAIN)
EVENT_OPENSKY_EXIT = '{}_exit'.format(DOMAIN)
SCAN_INTERVAL = timedelta(seconds=12)  # opensky public limit is 10 seconds

OPENSKY_ATTRIBUTION = "Information provided by the OpenSky Network "\
                      "(https://opensky-network.org)"
OPENSKY_API_URL = 'https://opensky-network.org/api/states/all'
OPENSKY_API_FIELDS = [
    'icao24', ATTR_CALLSIGN, 'origin_country', 'time_position',
    'time_velocity', ATTR_LONGITUDE, ATTR_LATITUDE, 'altitude',
    ATTR_ON_GROUND, 'velocity', 'heading', 'vertical_rate', 'sensors']


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RADIUS): vol.Coerce(float),
    vol.Optional(CONF_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Open Sky platform."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    add_devices([OpenSkySensor(
        hass, config.get(CONF_NAME, DOMAIN), latitude, longitude,
        config.get(CONF_RADIUS))], True)


class OpenSkySensor(Entity):
    """Open Sky Network Sensor."""

    def __init__(self, hass, name, latitude, longitude, radius):
        """Initialize the sensor."""
        self._session = requests.Session()
        self._latitude = latitude
        self._longitude = longitude
        self._radius = util_distance.convert(
            radius, LENGTH_KILOMETERS, LENGTH_METERS)
        self._state = 0
        self._hass = hass
        self._name = name
        self._previously_tracked = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _handle_boundary(self, callsigns, event):
        """Handle flights crossing region boundary."""
        for callsign in callsigns:
            data = {
                ATTR_CALLSIGN: callsign,
                ATTR_SENSOR: self._name,
            }
            self._hass.bus.fire(event, data)

    def update(self):
        """Update device state."""
        currently_tracked = set()
        states = self._session.get(OPENSKY_API_URL).json().get(ATTR_STATES)
        for state in states:
            data = dict(zip(OPENSKY_API_FIELDS, state))
            missing_location = (
                data.get(ATTR_LONGITUDE) is None or
                data.get(ATTR_LATITUDE) is None)
            if missing_location:
                continue
            if data.get(ATTR_ON_GROUND):
                continue
            distance = util_location.distance(
                self._latitude, self._longitude,
                data.get(ATTR_LATITUDE), data.get(ATTR_LONGITUDE))
            if distance is None or distance > self._radius:
                continue
            callsign = data[ATTR_CALLSIGN].strip()
            if callsign == '':
                continue
            currently_tracked.add(callsign)
        if self._previously_tracked is not None:
            entries = currently_tracked - self._previously_tracked
            exits = self._previously_tracked - currently_tracked
            self._handle_boundary(entries, EVENT_OPENSKY_ENTRY)
            self._handle_boundary(exits, EVENT_OPENSKY_EXIT)
        self._state = len(currently_tracked)
        self._previously_tracked = currently_tracked

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: OPENSKY_ATTRIBUTION
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'flights'

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:airplane'
