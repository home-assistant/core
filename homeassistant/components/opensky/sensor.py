"""Sensor for the Open Sky Network."""
from datetime import timedelta
import logging

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
ATTR_CALLSIGN = "callsign"
ATTR_ALTITUDE = "altitude"
ATTR_ON_GROUND = "on_ground"
ATTR_SENSOR = "sensor"
ATTR_STATES = "states"
ATTR_OP_IATA = "operatorIata"
ATTR_FLIGHT_NUMBER = "flightNumber"

DOMAIN = "opensky"

DEFAULT_ALTITUDE = 0

EVENT_OPENSKY_ENTRY = f"{DOMAIN}_entry"
EVENT_OPENSKY_EXIT = f"{DOMAIN}_exit"
SCAN_INTERVAL = timedelta(seconds=15)  # opensky public limit is 10 seconds

OPENSKY_ATTRIBUTION = (
    "Information provided by the OpenSky Network (https://opensky-network.org)"
)
OPENSKY_API_URL = "https://opensky-network.org/api/states/all"
OPENSKY_API_FIELDS = [
    ATTR_ICAO24,
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
# Api for route -> Flight Number
# e.g. https://opensky-network.org/api/routes?callsign=SAS125
OPENSKY_ROUTE_API_URL = "https://opensky-network.org/api/routes?callsign="
# Api for airplane meta data -> Registration etc
# e.g. https://opensky-network.org/api/metadata/aircraft/icao/4ac9f4
OPENSKY_AIRPLANE_META_API_URL = (
    "https://opensky-network.org/api/metadata/aircraft/icao/"
)

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

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _get_route(self, callsign):
        request = self._session.get(OPENSKY_ROUTE_API_URL + str(callsign))
        _LOGGER.debug("Route API status: %d", request.status_code)
        if request.status_code == 200:
            return request.json()
        return None

    def _get_plane_meta(self, icao24):
        request = self._session.get(OPENSKY_AIRPLANE_META_API_URL + str(icao24))
        _LOGGER.debug("Plane Meta API status: %d", request.status_code)
        if request.status_code == 200:
            return request.json()
        return None

    def _handle_boundary(self, flights, event, metadata):
        """Handle flights crossing region boundary."""
        for flight in flights:
            if flight in metadata:
                altitude = metadata[flight].get(ATTR_ALTITUDE)
                icao = metadata[flight].get(ATTR_ICAO24)
            else:
                # Assume Flight has landed if missing.
                altitude = 0
                icao = ""

            if flight in metadata and metadata[flight].get(ATTR_CALLSIGN) != "":
                _LOGGER.debug(
                    "Fetching route for callsign %s",
                    str(metadata[flight].get(ATTR_CALLSIGN)),
                )
                route = self._get_route(metadata[flight].get(ATTR_CALLSIGN))
                if route is not None:
                    flightnumber = str(route.get(ATTR_OP_IATA)) + str(
                        route.get(ATTR_FLIGHT_NUMBER)
                    )
                else:
                    flightnumber = ""
            else:
                route = None
                flightnumber = ""
            _LOGGER.debug("Flight: %s", flightnumber)

            if flight in metadata and metadata[flight].get(ATTR_ICAO24) != "":
                planemeta = self._get_plane_meta(metadata[flight].get(ATTR_ICAO24))
            else:
                planemeta = None

            data = {
                ATTR_ICAO24: icao,
                ATTR_CALLSIGN: flight,
                "fligh": flightnumber,
                ATTR_ALTITUDE: altitude,
                ATTR_SENSOR: self._name,
            }
            if route is not None:
                # Merge all route info into data dictionary
                data = {**data, **route}
            if planemeta is not None:
                data = {**data, **planemeta}
            _LOGGER.debug("Fire event for: %s", str(data))
            self._hass.bus.fire(event, data)

    def update(self):
        """Update device state."""
        currently_tracked = set()
        flight_metadata = {}
        states = self._session.get(OPENSKY_API_URL).json().get(ATTR_STATES)
        _LOGGER.debug("%d flights parsed", len(states))
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
