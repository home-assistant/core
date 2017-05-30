"""
Support for transport.opendata.ch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_public_transport/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://transport.opendata.ch/v1/'

ATTR_DEPARTURE_TIME1 = 'next_departure'
ATTR_DEPARTURE_TIME2 = 'next_on_departure'
ATTR_REMAINING_TIME = 'remaining_time'
ATTR_START = 'start'
ATTR_TARGET = 'destination'

CONF_ATTRIBUTION = "Data provided by transport.opendata.ch"
CONF_DESTINATION = 'to'
CONF_START = 'from'

DEFAULT_NAME = 'Next Departure'
ICON = 'mdi:bus'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_START): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Swiss public transport sensor."""
    name = config.get(CONF_NAME)
    # journal contains [0] Station ID start, [1] Station ID destination
    # [2] Station name start, and [3] Station name destination
    journey = [config.get(CONF_START), config.get(CONF_DESTINATION)]
    try:
        for location in [config.get(CONF_START), config.get(CONF_DESTINATION)]:
            # transport.opendata.ch doesn't play nice with requests.Session
            result = requests.get(
                '{}locations?query={}'.format(_RESOURCE, location), timeout=10)
            journey.append(result.json()['stations'][0]['name'])
    except KeyError:
        _LOGGER.exception(
            "Unable to determine stations. "
            "Check your settings and/or the availability of opendata.ch")
        return False

    data = PublicTransportData(journey)
    add_devices([SwissPublicTransportSensor(data, journey, name)])


class SwissPublicTransportSensor(Entity):
    """Implementation of an Swiss public transport sensor."""

    def __init__(self, data, journey, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._from = journey[2]
        self._to = journey[3]
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
                ATTR_DEPARTURE_TIME1: self._times[0],
                ATTR_DEPARTURE_TIME2: self._times[1],
                ATTR_START: self._from,
                ATTR_TARGET: self._to,
                ATTR_REMAINING_TIME: '{}'.format(
                    ':'.join(str(self._times[2]).split(':')[:2])),
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from opendata.ch and update the states."""
        self.data.update()
        self._times = self.data.times
        try:
            self._state = self._times[0]
        except TypeError:
            pass


class PublicTransportData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, journey):
        """Initialize the data object."""
        self.start = journey[0]
        self.destination = journey[1]
        self.times = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from opendata.ch."""
        response = requests.get(
            _RESOURCE +
            'connections?' +
            'from=' + self.start + '&' +
            'to=' + self.destination + '&' +
            'fields[]=connections/from/departureTimestamp/&' +
            'fields[]=connections/',
            timeout=10)
        connections = response.json()['connections'][:2]

        try:
            self.times = [
                dt_util.as_local(
                    dt_util.utc_from_timestamp(
                        item['from']['departureTimestamp'])).strftime(
                            TIME_STR_FORMAT)
                for item in connections
            ]
            self.times.append(
                dt_util.as_local(
                    dt_util.utc_from_timestamp(
                        connections[0]['from']['departureTimestamp'])) -
                dt_util.as_local(dt_util.utcnow()))
        except KeyError:
            self.times = ['n/a']
