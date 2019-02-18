"""
Support for real-time departure information for Rhein-Main public transport.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rmvtransport/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['PyRMVtransport==0.1.3']

_LOGGER = logging.getLogger(__name__)

CONF_NEXT_DEPARTURE = 'next_departure'

CONF_STATION = 'station'
CONF_DESTINATIONS = 'destinations'
CONF_DIRECTION = 'direction'
CONF_LINES = 'lines'
CONF_PRODUCTS = 'products'
CONF_TIME_OFFSET = 'time_offset'
CONF_MAX_JOURNEYS = 'max_journeys'
CONF_TIMEOUT = 'timeout'

DEFAULT_NAME = 'RMV Journey'

VALID_PRODUCTS = ['U-Bahn', 'Tram', 'Bus', 'S', 'RB', 'RE', 'EC', 'IC', 'ICE']

ICONS = {
    'U-Bahn': 'mdi:subway',
    'Tram': 'mdi:tram',
    'Bus': 'mdi:bus',
    'S': 'mdi:train',
    'RB': 'mdi:train',
    'RE': 'mdi:train',
    'EC': 'mdi:train',
    'IC': 'mdi:train',
    'ICE': 'mdi:train',
    'SEV': 'mdi:checkbox-blank-circle-outline',
    None: 'mdi:clock'
}
ATTRIBUTION = "Data provided by opendata.rmv.de"

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NEXT_DEPARTURE): [{
        vol.Required(CONF_STATION): cv.string,
        vol.Optional(CONF_DESTINATIONS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DIRECTION): cv.string,
        vol.Optional(CONF_LINES, default=[]):
            vol.All(cv.ensure_list, [cv.positive_int, cv.string]),
        vol.Optional(CONF_PRODUCTS, default=VALID_PRODUCTS):
            vol.All(cv.ensure_list, [vol.In(VALID_PRODUCTS)]),
        vol.Optional(CONF_TIME_OFFSET, default=0): cv.positive_int,
        vol.Optional(CONF_MAX_JOURNEYS, default=5): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}],
    vol.Optional(CONF_TIMEOUT, default=10): cv.positive_int
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the RMV departure sensor."""
    timeout = config.get(CONF_TIMEOUT)

    session = async_get_clientsession(hass)

    sensors = []
    for next_departure in config.get(CONF_NEXT_DEPARTURE):
        sensors.append(
            RMVDepartureSensor(
                session,
                next_departure[CONF_STATION],
                next_departure.get(CONF_DESTINATIONS),
                next_departure.get(CONF_DIRECTION),
                next_departure.get(CONF_LINES),
                next_departure.get(CONF_PRODUCTS),
                next_departure.get(CONF_TIME_OFFSET),
                next_departure.get(CONF_MAX_JOURNEYS),
                next_departure.get(CONF_NAME),
                timeout))

    tasks = [sensor.async_update() for sensor in sensors]
    if tasks:
        await asyncio.wait(tasks)
    if not all(sensor.data.departures for sensor in sensors):
        raise PlatformNotReady

    async_add_entities(sensors)


class RMVDepartureSensor(Entity):
    """Implementation of an RMV departure sensor."""

    def __init__(self, session, station, destinations, direction, lines,
                 products, time_offset, max_journeys, name, timeout):
        """Initialize the sensor."""
        self._station = station
        self._name = name
        self._state = None
        self.data = RMVDepartureData(session, station, destinations,
                                     direction, lines, products, time_offset,
                                     max_journeys, timeout)
        self._icon = ICONS[None]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        try:
            return {
                'next_departures': [val for val in self.data.departures[1:]],
                'direction': self.data.departures[0].get('direction'),
                'line': self.data.departures[0].get('line'),
                'minutes': self.data.departures[0].get('minutes'),
                'departure_time':
                    self.data.departures[0].get('departure_time'),
                'product': self.data.departures[0].get('product'),
            }
        except IndexError:
            return {}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "min"

    async def async_update(self):
        """Get the latest data and update the state."""
        await self.data.async_update()

        if not self.data.departures:
            self._state = None
            self._icon = ICONS[None]
            return
        if self._name == DEFAULT_NAME:
            self._name = self.data.station
        self._station = self.data.station
        self._state = self.data.departures[0].get('minutes')
        self._icon = ICONS[self.data.departures[0].get('product')]


class RMVDepartureData:
    """Pull data from the opendata.rmv.de web page."""

    def __init__(self, session, station_id, destinations, direction, lines,
                 products, time_offset, max_journeys, timeout):
        """Initialize the sensor."""
        from RMVtransport import RMVtransport

        self.station = None
        self._station_id = station_id
        self._destinations = destinations
        self._direction = direction
        self._lines = lines
        self._products = products
        self._time_offset = time_offset
        self._max_journeys = max_journeys
        self.rmv = RMVtransport(session, timeout)
        self.departures = []

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Update the connection data."""
        from RMVtransport.rmvtransport import RMVtransportApiConnectionError

        try:
            _data = await self.rmv.get_departures(self._station_id,
                                                  products=self._products,
                                                  directionId=self._direction,
                                                  maxJourneys=50)
        except RMVtransportApiConnectionError:
            self.departures = []
            _LOGGER.warning("Could not retrive data from rmv.de")
            return
        self.station = _data.get('station')
        _deps = []
        for journey in _data['journeys']:
            # find the first departure meeting the criteria
            _nextdep = {ATTR_ATTRIBUTION: ATTRIBUTION}
            if self._destinations:
                dest_found = False
                for dest in self._destinations:
                    if dest in journey['stops']:
                        dest_found = True
                        _nextdep['destination'] = dest
                if not dest_found:
                    continue
            elif self._lines and journey['number'] not in self._lines:
                continue
            elif journey['minutes'] < self._time_offset:
                continue
            for attr in ['direction', 'departure_time', 'product', 'minutes']:
                _nextdep[attr] = journey.get(attr, '')
            _nextdep['line'] = journey.get('number', '')
            _deps.append(_nextdep)
            if len(_deps) > self._max_journeys:
                break
        self.departures = _deps
