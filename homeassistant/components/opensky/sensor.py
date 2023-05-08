"""Sensor for the Open Sky Network."""
from __future__ import annotations

from datetime import timedelta
import math

from python_opensky import BoundingBox, OpenSky
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.location import AXIS_A, FLATTENING

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
# OpenSky free user has 400 credits, with 4 credits per API call. 100/24 = ~4 requests per hour
SCAN_INTERVAL = timedelta(minutes=15)

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


def calculate_point(
    latitude: float, longitude: float, distance: float, degrees: float
) -> tuple[float, float]:
    """Calculate a point from an origin point, direction in degrees and distance."""
    # pylint: disable=invalid-name
    piD4 = math.atan(1.0)
    two_pi = piD4 * 8.0
    latitude = latitude * piD4 / 45.0
    longitude = longitude * piD4 / 45.0
    degrees = degrees * piD4 / 45.0
    if degrees < 0.0:
        degrees = degrees + two_pi
    if degrees > two_pi:
        degrees = degrees - two_pi
    AXIS_B = AXIS_A * (1.0 - FLATTENING)
    TanU1 = (1 - FLATTENING) * math.tan(latitude)
    U1 = math.atan(TanU1)
    sigma1 = math.atan2(TanU1, math.cos(degrees))
    Sinalpha = math.cos(U1) * math.sin(degrees)
    cosalpha_sq = 1.0 - Sinalpha * Sinalpha
    u2 = cosalpha_sq * (AXIS_A * AXIS_A - AXIS_B * AXIS_B) / (AXIS_B * AXIS_B)
    A = 1.0 + (u2 / 16384) * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = (u2 / 1024) * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    # Starting with the approx
    sigma = distance / (AXIS_B * A)
    last_sigma = 2.0 * sigma + 2.0  # something impossible

    # Iterate the following 3 eqs until no sig change in sigma
    # two_sigma_m , delta_sigma
    while abs((last_sigma - sigma) / sigma) > 1.0e-9:
        two_sigma_m = 2 * sigma1 + sigma
        delta_sigma = (
            B
            * math.sin(sigma)
            * (
                math.cos(two_sigma_m)
                + (B / 4)
                * (
                    math.cos(sigma)
                    * (
                        -1
                        + 2 * math.pow(math.cos(two_sigma_m), 2)
                        - (B / 6)
                        * math.cos(two_sigma_m)
                        * (-3 + 4 * math.pow(math.sin(sigma), 2))
                        * (-3 + 4 * math.pow(math.cos(two_sigma_m), 2))
                    )
                )
            )
        )
        last_sigma = sigma
        sigma = (distance / (AXIS_B * A)) + delta_sigma
    phi2 = math.atan2(
        (
            math.sin(U1) * math.cos(sigma)
            + math.cos(U1) * math.sin(sigma) * math.cos(degrees)
        ),
        (
            (1 - FLATTENING)
            * math.sqrt(
                math.pow(Sinalpha, 2)
                + pow(
                    math.sin(U1) * math.sin(sigma)
                    - math.cos(U1) * math.cos(sigma) * math.cos(degrees),
                    2,
                )
            )
        ),
    )
    lembda = math.atan2(
        (math.sin(sigma) * math.sin(degrees)),
        (
            math.cos(U1) * math.cos(sigma)
            - math.sin(U1) * math.sin(sigma) * math.cos(degrees)
        ),
    )
    C = (FLATTENING / 16) * cosalpha_sq * (4 + FLATTENING * (4 - 3 * cosalpha_sq))
    omega = lembda - (1 - C) * FLATTENING * Sinalpha * (
        sigma
        + C
        * math.sin(sigma)
        * (
            math.cos(two_sigma_m)
            + C * math.cos(sigma) * (-1 + 2 * math.pow(math.cos(two_sigma_m), 2))
        )
    )
    lembda2 = longitude + omega
    alpha21 = math.atan2(
        Sinalpha,
        (
            -math.sin(U1) * math.sin(sigma)
            + math.cos(U1) * math.cos(sigma) * math.cos(degrees)
        ),
    )
    alpha21 = alpha21 + two_pi / 2.0
    if alpha21 < 0.0:
        alpha21 = alpha21 + two_pi
    if alpha21 > two_pi:
        alpha21 = alpha21 - two_pi
    phi2 = phi2 * 45.0 / piD4
    lembda2 = lembda2 * 45.0 / piD4
    return phi2, lembda2


def get_bounding_box(latitude: float, longitude: float, radius: float) -> BoundingBox:
    """Get bounding box from radius and a point."""
    north = calculate_point(latitude, longitude, radius, 0)
    east = calculate_point(latitude, longitude, radius, 90)
    south = calculate_point(latitude, longitude, radius, 180)
    west = calculate_point(latitude, longitude, radius, 270)
    return BoundingBox(
        min_latitude=min(north[0], south[0]) + latitude,
        max_latitude=max(north[0], south[0]) + latitude,
        min_longitude=min(east[1], west[1]) + longitude,
        max_longitude=max(east[1], west[1]) + longitude,
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
    radius = config.get(CONF_RADIUS, 0)
    bounding_box = get_bounding_box(latitude, longitude, radius)
    session = async_get_clientsession(hass)
    opensky = OpenSky(session=session)
    add_entities(
        [
            OpenSkySensor(
                hass,
                config.get(CONF_NAME, DOMAIN),
                opensky,
                bounding_box,
                config.get(CONF_ALTITUDE),
            )
        ],
        True,
    )


class OpenSkySensor(SensorEntity):
    """Open Sky Network Sensor."""

    _attr_attribution = (
        "Information provided by the OpenSky Network (https://opensky-network.org)"
    )

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        opensky: OpenSky,
        bounding_box: BoundingBox,
        altitude: float | None,
    ) -> None:
        """Initialize the sensor."""
        self._altitude = altitude or 0
        self._state = 0
        self._hass = hass
        self._name = name
        self._previously_tracked: set[str] = set()
        self._opensky = opensky
        self._bounding_box = bounding_box

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
                altitude = metadata[flight].barometric_altitude
                longitude = metadata[flight].longitude
                latitude = metadata[flight].latitude
                icao24 = metadata[flight].icao24
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

    async def async_update(self) -> None:
        """Update device state."""
        currently_tracked = set()
        flight_metadata = {}
        response = await self._opensky.get_states(bounding_box=self._bounding_box)
        for flight in response.states:
            if not flight.callsign:
                continue
            callsign = flight.callsign.strip()
            if callsign != "":
                flight_metadata[callsign] = flight
            else:
                continue
            if (
                flight.longitude is None
                or flight.latitude is None
                or flight.on_ground
                or flight.barometric_altitude is None
            ):
                continue
            altitude = flight.barometric_altitude
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
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return "flights"

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:airplane"
