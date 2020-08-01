"""Sensor for the Open Sky Network."""
from datetime import timedelta
import logging
import math

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import distance as util_distance, location as util_location

_LOGGER = logging.getLogger(__name__)

CONF_ALTITUDE = "altitude"

ATTR_CALLSIGN = "callsign"
ATTR_ALTITUDE = "altitude"
ATTR_ON_GROUND = "on_ground"
ATTR_SENSOR = "sensor"
ATTR_STATES = "states"

DOMAIN = "opensky"

DEFAULT_ALTITUDE = 0

EVENT_OPENSKY_ENTRY = f"{DOMAIN}_entry"
EVENT_OPENSKY_EXIT = f"{DOMAIN}_exit"
SCAN_INTERVAL = timedelta(seconds=12)  # opensky public limit is 10 seconds

OPENSKY_ATTRIBUTION = (
    "Information provided by the OpenSky Network (https://opensky-network.org)"
)
OPENSKY_API_URL = "https://opensky-network.org/api/states/all"
OPENSKY_API_FIELDS = [
    "icao24",
    ATTR_CALLSIGN,
    "origin_country",
    "time_position",
    "time_velocity",
    ATTR_LONGITUDE,
    ATTR_LATITUDE,
    ATTR_ALTITUDE,
    ATTR_ON_GROUND,
    "velocity",
    "heading",
    "vertical_rate",
    "sensors",
]


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RADIUS): vol.Coerce(float),
        vol.Optional(CONF_NAME): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Optional(CONF_ALTITUDE, default=DEFAULT_ALTITUDE): vol.Coerce(float),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Open Sky platform."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    add_entities(
        [
            OpenSkySensor(
                hass,
                config.get(CONF_NAME, DOMAIN),
                latitude,
                longitude,
                config.get(CONF_RADIUS),
                config.get(CONF_ALTITUDE),
            )
        ],
        True,
    )


class OpenSkySensor(Entity):
    """Open Sky Network Sensor."""

    def __init__(self, hass, name, latitude, longitude, radius, altitude):
        """Initialize the sensor."""
        self._session = requests.Session()
        self._latitude = latitude
        self._longitude = longitude
        self._radius = util_distance.convert(radius, LENGTH_KILOMETERS, LENGTH_METERS)
        self._altitude = altitude
        self._state = 0
        self._hass = hass
        self._name = name
        self._previously_tracked = None
        self._params = {}
        self._calc_bbox()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _calc_bbox(self):
        """
        Calculate the rectangular bounding box for a circle on Earth's surface.

        Credit:
          - Based on code written in Java by Jan Matuschek:
            http://janmatuschek.de/LatitudeLongitudeBoundingCoordinates#Java
          - Later ported to Python by Jeremy Fein:
            https://github.com/jfein/PyGeoTools
        License: https://creativecommons.org/licenses/by/3.0/
        Changes: Adapted for Home Assistant's opensky sensor
        """
        MIN_LAT = math.radians(-90)
        MAX_LAT = math.radians(90)
        MIN_LON = math.radians(-180)
        MAX_LON = math.radians(180)

        rad_lat = math.radians(self._latitude)
        rad_lon = math.radians(self._longitude)

        # angular distance in radians on a great circle
        rad_dist = self._radius / util_location.AXIS_A

        min_lat = rad_lat - rad_dist
        max_lat = rad_lat + rad_dist

        if min_lat > MIN_LAT and max_lat < MAX_LAT:
            delta_lon = math.asin(math.sin(rad_dist) / math.cos(rad_lat))

            min_lon = rad_lon - delta_lon
            if min_lon < MIN_LON:
                min_lon += 2 * math.pi

            max_lon = rad_lon + delta_lon
            if max_lon > MAX_LON:
                max_lon -= 2 * math.pi
        # a pole is within the distance
        else:
            min_lat = max(min_lat, MIN_LAT)
            max_lat = min(max_lat, MAX_LAT)
            min_lon = MIN_LON
            max_lon = MAX_LON

        self._params["lamin"] = round(math.degrees(min_lat), 4)
        self._params["lomin"] = round(math.degrees(min_lon), 4)
        self._params["lamax"] = round(math.degrees(max_lat), 4)
        self._params["lomax"] = round(math.degrees(max_lon), 4)

    def _handle_boundary(self, flights, event, metadata):
        """Handle flights crossing region boundary."""
        for flight in flights:
            if flight in metadata:
                altitude = metadata[flight].get(ATTR_ALTITUDE)
            else:
                # Assume Flight has landed if missing.
                altitude = 0

            data = {
                ATTR_CALLSIGN: flight,
                ATTR_ALTITUDE: altitude,
                ATTR_SENSOR: self._name,
            }
            self._hass.bus.fire(event, data)

    def update(self):
        """Update device state."""
        currently_tracked = set()
        flight_metadata = {}
        states = (
            self._session.get(OPENSKY_API_URL, params=self._params)
            .json()
            .get(ATTR_STATES)
            or []
        )
        for state in states:
            flight = dict(zip(OPENSKY_API_FIELDS, state))
            callsign = flight[ATTR_CALLSIGN].strip()
            if callsign != "":
                flight_metadata[callsign] = flight
            else:
                continue
            missing_location = (
                flight.get(ATTR_LONGITUDE) is None or flight.get(ATTR_LATITUDE) is None
            )
            if missing_location:
                continue
            if flight.get(ATTR_ON_GROUND):
                continue
            distance = util_location.distance(
                self._latitude,
                self._longitude,
                flight.get(ATTR_LATITUDE),
                flight.get(ATTR_LONGITUDE),
            )
            if distance is None or distance > self._radius:
                continue
            altitude = flight.get(ATTR_ALTITUDE)
            if altitude > self._altitude and self._altitude != 0:
                continue
            currently_tracked.add(callsign)
        if self._previously_tracked is not None:
            entries = currently_tracked - self._previously_tracked
            exits = self._previously_tracked - currently_tracked
            self._handle_boundary(entries, EVENT_OPENSKY_ENTRY, flight_metadata)
            self._handle_boundary(exits, EVENT_OPENSKY_EXIT, flight_metadata)
        self._state = len(currently_tracked)
        self._previously_tracked = currently_tracked

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: OPENSKY_ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "flights"

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:airplane"
