"""
"""
import logging
from datetime import timedelta, datetime

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_BUS = 'bus'
ATTR_ROUTE = 'route'
ATTR_STOP = 'stop'
ATTR_ARRIVAL = 'arrival'
ATTR_DIRECTION = 'direction'

CONF_ATTRIBUTION = ""
CONF_BUS = 'bus'
CONF_LAT = 'lat'
CONF_LON = 'lon'
CONF_DIRECTION = 'direction'

DEFAULT_NAME = 'Next Bus'
ICON = 'mdi:bus'

SCAN_INTERVAL = timedelta(minutes=1)
TIME_STR_FORMAT = '%H:%M'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_BUS): cv.string,
    vol.Required(CONF_LAT): cv.string,
    vol.Required(CONF_LON): cv.string,
    vol.Optional(CONF_DIRECTION): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the OASA public transport sensor."""
    name = config.get(CONF_NAME)
    bus = config.get(CONF_BUS)
    lat = config.get(CONF_LAT)
    lon = config.get(CONF_LON)
    direction = config.get(CONF_DIRECTION)

    data = PublicTransportData(bus, lat, lon, direction)
    add_devices([OASAPublicTransportSensor(data, name)], True)


class OASAPublicTransportSensor(Entity):
    """Implementation of an Dublin public transport sensor."""

    def __init__(self, data, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
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
                ATTR_BUS: self._times[0][ATTR_BUS],
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_STOP: self._times[0][ATTR_STOP],
                ATTR_DIRECTION: self._times[0][ATTR_DIRECTION],
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
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
        """Get the latest data from oasa api."""
        self.data.update()
        self._times = self.data.info
        try:
            self._state = self._times[0][ATTR_ARRIVAL]
        except TypeError:
            pass


def getCompassDirection(degrees):
    degrees = int(degrees)
    direction = "n/a"
    direction2 = "n/a"
    if 315 <= degrees <= 45:
        direction = "N"
    elif 45 <= degrees <= 135:
        direction = "E"
    elif 135 <= degrees <= 225:
        direction = "S"
    elif 225 <= degrees <= 315:
        direction = "W"

    if 0 <= degrees <= 90:
        direction2 = "NE"
    elif 90 <= degrees <= 180:
        direction2 = "SE"
    elif 180 <= degrees <= 270:
        direction2 = "SW"
    elif 270 <= degrees <= 360:
        direction2 = "NW"

    return direction, direction2


class PublicTransportData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, bus, lat, lon, direction):
        """Initialize the data object."""
        if type(bus) == str or type(bus) == int:
            self.bus = [str(bus)]
        else:
            self.bus = bus
        self.lat = lat
        self.lon = lon
        self.direction = direction
        self.info = [{ATTR_BUS: 'n/a',
                      ATTR_ROUTE: 'n/a',
                      ATTR_STOP: 'n/a',
                      ATTR_ARRIVAL: 'n/a',
                      ATTR_DIRECTION: 'n/a'}]

    def update(self):
        """Get the info of the bus and bus stop."""
        findlines = self.bus
        findlat = self.lat
        findlon = self.lon

        bussesFound = []

        myrequest = "http://telematics.oasa.gr/api/?act=webGetLinesWithMLInfo"
        lines = requests.post(myrequest, timeout=10).json()
        for line in lines:
            if line["line_id"] in findlines:
                myrequest = "http://telematics.oasa.gr/api/?act=getRoutesForLine&p1={linecode}".format(
                    linecode=line['line_code'])
                routes = requests.post(myrequest, timeout=10).json()
                for route in routes:
                    myrequest = "http://telematics.oasa.gr/api/?act=webGetStops&p1={routecode}".format(
                        routecode=route['route_code'])
                    stops = requests.post(myrequest, timeout=10).json()
                    minDist = 10000
                    closest = None
                    for stop in stops:
                        distance = abs(float(
                            findlat) - float(stop['StopLat']) + float(findlon) - float(stop['StopLng']))
                        if distance < minDist:
                            minDist = distance
                            closest = stop
                    myrequest = "http://telematics.oasa.gr/api/?act=getStopArrivals&p1={stopcode}".format(
                        stopcode=closest['StopCode'])
                    arrivals = requests.post(myrequest, timeout=10).json()
                    if arrivals is not None:
                        for arrival in arrivals:
                            if arrival['route_code'] == route['route_code']:
                                bussesFound.append({
                                    ATTR_BUS: line['line_id'],
                                    ATTR_ROUTE: route['route_descr'],
                                    ATTR_STOP: closest['StopDescr'],
                                    ATTR_ARRIVAL: arrival['btime2'],
                                    ATTR_DIRECTION: closest['StopHeading']
                                })

        bussesFound = sorted(bussesFound, key=lambda k: int(k[ATTR_ARRIVAL]))
        self.info = bussesFound

        if not self.info:
            self.info = [{ATTR_BUS: 'n/a',
                          ATTR_ROUTE: 'n/a',
                          ATTR_STOP: 'n/a',
                          ATTR_ARRIVAL: 'n/a',
                          ATTR_DIRECTION: 'n/a'}]
