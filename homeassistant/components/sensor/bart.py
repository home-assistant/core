"""
Support for the BART (Bay Area Rapid Transit) API.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bart/
"""
import logging
from datetime import timedelta

import requests

from bs4 import BeautifulSoup

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['beautifulsoup4==4.4.1', 'lxml==3.6.0']

ATTR_DEPARTURE_TIME1 = 'first_departure_time_minutes'
ATTR_DEPARTURE_TIME2 = 'second_departure_time_minutes'
ATTR_DEPARTURE_TIME3 = 'third_departure_time_minutes'
ATTR_LENGTH1 = 'first_departure_train_length'
ATTR_LENGTH2 = 'second_departure_train_length'
ATTR_LENGTH3 = 'third_departure_train_length'
ATTR_LINE1 = 'first_departure_line'
ATTR_LINE2 = 'second_departure_line'
ATTR_LINE3 = 'third_departure_line'
ATTR_ADVISORY = 'service_advisory'
ATTR_ORIGIN = 'origin_station'
ATTR_LINES = 'lines'
ICON = 'mdi:train'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the BART public transport sensor."""
    journey = [config.get('origin'), config.get('lines')]
    dev = []
    data = PublicTransportData(journey)
    dev.append(BARTPublicTransportSensor(data, journey))
    add_devices(dev)


# pylint: disable=too-few-public-methods
class BARTPublicTransportSensor(Entity):
    """Implementation of an Swiss public transport sensor."""

    def __init__(self, data, journey):
        """Initialize the sensor."""
        self.data = data
        self._name = 'Next BART Departure'
        self._from = journey[0]
        self._advisories = ['No active advisories']
        self._lines = journey[1]
        self.update()

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
                ATTR_LINE1: self._times[0][0],
                ATTR_LINE2: self._times[1][0],
                ATTR_LINE3: self._times[2][0],
                ATTR_DEPARTURE_TIME1: self._times[0][1],
                ATTR_DEPARTURE_TIME2: self._times[1][1],
                ATTR_DEPARTURE_TIME3: self._times[2][1],
                ATTR_LENGTH1: self._times[0][2],
                ATTR_LENGTH2: self._times[1][2],
                ATTR_LENGTH3: self._times[2][2],
                ATTR_ADVISORY: ", ".join(self._advisories),
                ATTR_ORIGIN: self._from,
                ATTR_LINES: ", ".join(self._lines),
            }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from the BART API and update the states."""
        self.data.update()
        self._times = sorted(self.data.times, key=lambda eta: eta[1])
        self._advisories = self.data.advisories
        try:
            self._state = self._times[0][1]
        except TypeError:
            pass


# pylint: disable=too-few-public-methods
class PublicTransportData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, journey):
        """Initialize the data object."""
        self.origin = journey[0]
        self.lines = journey[1]
        self.times = []
        self.advisories = []

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the BART API."""
        etdResponse = requests.get('http://api.bart.gov/api/etd.aspx?cmd=etd&key=MW9S-E7SL-26DU-VV8V&orig=' + self.origin, timeout=30)
        etdSoup = BeautifulSoup(etdResponse.text, "xml")
        try:
            self.times = []
            for etd in etdSoup.find_all('etd'):
              if etd.abbreviation.string in self.lines:
                for estimate in etd.find_all('estimate'):
                  self.times.append([etd.abbreviation.string,estimate.minutes.string,estimate.length.string])
        except KeyError:
            self.times = ['n/a']

        advisoryResponse = requests.get('http://api.bart.gov/api/bsa.aspx?cmd=bsa&key=MW9S-E7SL-26DU-VV8V&orig=' + self.origin, timeout=30)
        advisorySoup = BeautifulSoup(advisoryResponse.text, "xml")
        try:
            self.advisories = []
            for advisory in advisorySoup.find_all('bsa'):
              self.advisories.append(advisory.description.string)
        except KeyError:
            self.advisories = ['No active advisories']
