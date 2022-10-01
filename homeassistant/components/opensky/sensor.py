"""Sensor for the Open Sky Network."""
from __future__ import annotations

from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
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
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import location as util_location
from homeassistant.util.unit_conversion import DistanceConverter

CONF_ALTITUDE = "altitude"

ATTR_ICAO24 = "icao24"
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


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RADIUS): vol.Coerce(float),
        vol.Optional(CONF_NAME): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Optional(CONF_ALTITUDE, default=DEFAULT_ALTITUDE): vol.Coerce(float),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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


class OpenSkySensor(SensorEntity):
    """Open Sky Network Sensor."""

    def __init__(self, hass, name, latitude, longitude, radius, altitude):
        """Initialize the sensor."""
        self._session = requests.Session()
        self._latitude = latitude
        self._longitude = longitude
        self._radius = DistanceConverter.convert(
            radius, LENGTH_KILOMETERS, LENGTH_METERS
        )
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
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    def _handle_boundary(self, flights, event, metadata):
        """Handle flights crossing region boundary."""
        for flight in flights:
            if flight in metadata:
                altitude = metadata[flight].get(ATTR_ALTITUDE)
                longitude = metadata[flight].get(ATTR_LONGITUDE)
                latitude = metadata[flight].get(ATTR_LATITUDE)
                icao24 = metadata[flight].get(ATTR_ICAO24)
            else:
                # Assume Flight has landed if missing.
                altitude = 0
                longitude = None
                latitude = None
                icao24 = None

            data = {
                ATTR_CALLSIGN: flight,
                ATTR_ALTITUDE: altitude,
                ATTR_SENSOR: self._name,
                ATTR_LONGITUDE: longitude,
                ATTR_LATITUDE: latitude,
                ATTR_ICAO24: icao24,
            }
            self._hass.bus.fire(event, data)

    def update(self) -> None:
        """Update device state."""
        currently_tracked = set()
        flight_metadata = {}
        states = self._session.get(OPENSKY_API_URL).json().get(ATTR_STATES)
        for state in states:
            flight = dict(zip(OPENSKY_API_FIELDS, state))
            callsign = flight[ATTR_CALLSIGN].strip()
            if callsign != "":
                flight_metadata[callsign] = flight
            else:
                continue
            if (
                (longitude := flight.get(ATTR_LONGITUDE)) is None
                or (latitude := flight.get(ATTR_LATITUDE)) is None
                or flight.get(ATTR_ON_GROUND)
            ):
                continue
            distance = util_location.distance(
                self._latitude,
                self._longitude,
                latitude,
                longitude,
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
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: OPENSKY_ATTRIBUTION}

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return "flights"

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:airplane"
