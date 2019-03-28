"""
Support for Nederlandse Spoorwegen public transport.

For more details on this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nederlandse_spoorwegen/
"""
from datetime import datetime, timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_EMAIL, CONF_NAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['nsapi==2.7.4']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by NS"
CONF_ROUTES = 'routes'
CONF_FROM = 'from'
CONF_TO = 'to'
CONF_VIA = 'via'

ICON = 'mdi:train'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

ROUTE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_FROM): cv.string,
    vol.Required(CONF_TO): cv.string,
    vol.Optional(CONF_VIA): cv.string})

ROUTES_SCHEMA = vol.All(
    cv.ensure_list,
    [ROUTE_SCHEMA])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_ROUTES): ROUTES_SCHEMA,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the departure sensor."""
    import ns_api
    nsapi = ns_api.NSAPI(
        config.get(CONF_EMAIL), config.get(CONF_PASSWORD))
    try:
        stations = nsapi.get_stations()
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError) as error:
        _LOGGER.error("Couldn't fetch stations, API password correct?: %s",
                      error)
        return

    sensors = []
    for departure in config.get(CONF_ROUTES):
        if(not valid_stations(stations, [departure.get(CONF_FROM),
                                         departure.get(CONF_VIA),
                                         departure.get(CONF_TO)])):
            continue
        sensors.append(
            NSDepartureSensor(
                nsapi, departure.get(CONF_NAME), departure.get(CONF_FROM),
                departure.get(CONF_TO), departure.get(CONF_VIA)))
    if sensors:
        add_entities(sensors, True)


def valid_stations(stations, given_stations):
    """Verify the existence of the given station codes."""
    for station in given_stations:
        if station is None:
            continue
        if not any(s.code == station.upper() for s in stations):
            _LOGGER.warning("Station '%s' is not a valid station.", station)
            return False
    return True


class NSDepartureSensor(Entity):
    """Implementation of a NS Departure Sensor."""

    def __init__(self, nsapi, name, departure, heading, via):
        """Initialize the sensor."""
        self._nsapi = nsapi
        self._name = name
        self._departure = departure
        self._via = via
        self._heading = heading
        self._state = None
        self._trips = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self._trips:
            return

        if self._trips[0].trip_parts:
            route = [self._trips[0].departure]
            for k in self._trips[0].trip_parts:
                route.append(k.destination)

        return {
            'going': self._trips[0].going,
            'departure_time_planned':
                self._trips[0].departure_time_planned.strftime('%H:%M'),
            'departure_time_actual':
                self._trips[0].departure_time_actual.strftime('%H:%M'),
            'departure_delay':
                self._trips[0].departure_time_planned !=
                self._trips[0].departure_time_actual,
            'departure_platform':
                self._trips[0].trip_parts[0].stops[0].platform,
            'departure_platform_changed':
                self._trips[0].trip_parts[0].stops[0].platform_changed,
            'arrival_time_planned':
                self._trips[0].arrival_time_planned.strftime('%H:%M'),
            'arrival_time_actual':
                self._trips[0].arrival_time_actual.strftime('%H:%M'),
            'arrival_delay':
                self._trips[0].arrival_time_planned !=
                self._trips[0].arrival_time_actual,
            'arrival_platform':
                self._trips[0].trip_parts[0].stops[-1].platform,
            'arrival_platform_changed':
                self._trips[0].trip_parts[0].stops[-1].platform_changed,
            'next':
                self._trips[1].departure_time_actual.strftime('%H:%M'),
            'status': self._trips[0].status.lower(),
            'transfers': self._trips[0].nr_transfers,
            'route': route,
            'remarks': [r.message for r in self._trips[0].trip_remarks],
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the trip information."""
        try:
            self._trips = self._nsapi.get_trips(
                datetime.now().strftime("%d-%m-%Y %H:%M"),
                self._departure, self._via, self._heading,
                True, 0)
            if self._trips:
                actual_time = self._trips[0].departure_time_actual
                self._state = actual_time.strftime('%H:%M')
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as error:
            _LOGGER.error("Couldn't fetch trip info: %s", error)
