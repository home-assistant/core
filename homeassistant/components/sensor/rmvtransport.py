"""
Support for real-time departure information for Rhein-Main public transport.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rmvtransport/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION)

REQUIREMENTS = ['PyRMVtransport==0.0.7']

_LOGGER = logging.getLogger(__name__)

CONF_NEXT_DEPARTURE = 'next_departure'

CONF_STATION = 'station'
CONF_DESTINATIONS = 'destinations'
CONF_DIRECTIONS = 'directions'
CONF_LINES = 'lines'
CONF_PRODUCTS = 'products'
CONF_TIME_OFFSET = 'time_offset'
CONF_MAX_JOURNEYS = 'max_journeys'

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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NEXT_DEPARTURE): [{
        vol.Required(CONF_STATION): cv.string,
        vol.Optional(CONF_DESTINATIONS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DIRECTIONS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_LINES, default=[]):
            vol.All(cv.ensure_list, [cv.positive_int, cv.string]),
        vol.Optional(CONF_PRODUCTS, default=VALID_PRODUCTS):
            vol.All(cv.ensure_list, [vol.In(VALID_PRODUCTS)]),
        vol.Optional(CONF_TIME_OFFSET, default=0): cv.positive_int,
        vol.Optional(CONF_MAX_JOURNEYS, default=5): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}]
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RMV departure sensor."""
    sensors = []
    for next_departure in config.get(CONF_NEXT_DEPARTURE):
        sensors.append(
            RMVDepartureSensor(
                next_departure[CONF_STATION],
                next_departure.get(CONF_DESTINATIONS),
                next_departure.get(CONF_DIRECTIONS),
                next_departure.get(CONF_LINES),
                next_departure.get(CONF_PRODUCTS),
                next_departure.get(CONF_TIME_OFFSET),
                next_departure.get(CONF_MAX_JOURNEYS),
                next_departure.get(CONF_NAME)))
    add_entities(sensors, True)


class RMVDepartureSensor(Entity):
    """Implementation of an RMV departure sensor."""

    def __init__(self, station, destinations, directions,
                 lines, products, time_offset, max_journeys, name):
        """Initialize the sensor."""
        self._station = station
        self._name = name
        self._state = None
        self.data = RMVDepartureData(station, destinations, directions, lines,
                                     products, time_offset, max_journeys)
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

    def update(self):
        """Get the latest data and update the state."""
        self.data.update()
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

    def __init__(self, station_id, destinations, directions,
                 lines, products, time_offset, max_journeys):
        """Initialize the sensor."""
        import RMVtransport
        self.station = None
        self._station_id = station_id
        self._destinations = destinations
        self._directions = directions
        self._lines = lines
        self._products = products
        self._time_offset = time_offset
        self._max_journeys = max_journeys
        self.rmv = RMVtransport.RMVtransport()
        self.departures = []

    def update(self):
        """Update the connection data."""
        try:
            _data = self.rmv.get_departures(self._station_id,
                                            products=self._products,
                                            maxJourneys=50)
        except ValueError:
            self.departures = []
            _LOGGER.warning("Returned data not understood")
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
