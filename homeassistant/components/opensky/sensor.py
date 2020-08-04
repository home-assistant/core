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

ATTR_ICAO24 = "icao24"
ATTR_ALTITUDE = "altitude"
ATTR_ON_GROUND = "on_ground"
ATTR_SENSOR = "sensor"
ATTR_STATES = "states"

DOMAIN = "opensky"

DEFAULT_ALTITUDE = 0

EVENT_OPENSKY_ENTRY = f"{DOMAIN}_entry"
EVENT_OPENSKY_EXIT = f"{DOMAIN}_exit"
SCAN_INTERVAL = timedelta(seconds=12)  # opensky public limit is 10 seconds

MIN_LAT = math.radians(-90)
MAX_LAT = math.radians(90)
MIN_LON = math.radians(-180)
MAX_LON = math.radians(180)

OPENSKY_ATTRIBUTION = (
    "Information provided by the OpenSky Network (https://opensky-network.org)"
)
OPENSKY_API_URL = "https://opensky-network.org/api/states/all"
OPENSKY_API_FIELDS = [
    ATTR_ICAO24,
    "callsign",
    "origin_country",
    "time_position",
    "last_contact",
    ATTR_LONGITUDE,
    ATTR_LATITUDE,
    ATTR_ALTITUDE,
    ATTR_ON_GROUND,
    "velocity",
    "true_track",
    "vertical_rate",
    "sensors",
    "geo_altitude",
    "squawk",
    "spi",
    "position_source",
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
        self._cache = {}
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
            if len(state) < len(OPENSKY_API_FIELDS):
                _LOGGER.warning("Skipping invalid state")
                continue

            flight = dict(zip(OPENSKY_API_FIELDS, state))

            icao24 = flight[ATTR_ICAO24]
            flight_metadata[icao24] = flight

            if flight[ATTR_ON_GROUND]:
                continue

            lat = flight[ATTR_LATITUDE]
            lon = flight[ATTR_LONGITUDE]
            if None in (lat, lon):
                continue

            distance = util_location.distance(self._latitude, self._longitude, lat, lon)
            if distance is None or distance > self._radius:
                continue

            altitude = flight[ATTR_ALTITUDE] or 0
            if altitude > self._altitude and self._altitude != 0:
                continue

            currently_tracked.add(icao24)

        self._cache.update(flight_metadata)
        if self._previously_tracked is not None:
            entries = currently_tracked - self._previously_tracked
            exits = self._previously_tracked - currently_tracked

            for flight in entries:
                self._hass.bus.fire(
                    EVENT_OPENSKY_ENTRY,
                    {**self._cache[flight], ATTR_SENSOR: self._name},
                )

            for flight in exits:
                self._hass.bus.fire(
                    EVENT_OPENSKY_EXIT, {**self._cache[flight], ATTR_SENSOR: self._name}
                )
                del self._cache[flight]

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
