"""
Support for transport.opendata.ch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_public_transport/
"""
import logging
from datetime import timedelta

import requests

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://transport.opendata.ch/v1/'

ATTR_DEPARTURE_TIME1 = 'Next departure'
ATTR_DEPARTURE_TIME2 = 'Next on departure'
ATTR_START = 'Start'
ATTR_TARGET = 'Destination'
ATTR_REMAINING_TIME = 'Remaining time'
ICON = 'mdi:bus'

TIME_STR_FORMAT = "%H:%M"

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the Swiss public transport sensor."""
    # journal contains [0] Station ID start, [1] Station ID destination
    # [2] Station name start, and [3] Station name destination
    journey = [config.get('from'), config.get('to')]
    try:
        for location in [config.get('from', None), config.get('to', None)]:
            # transport.opendata.ch doesn't play nice with requests.Session
            result = requests.get(_RESOURCE + 'locations?query=%s' % location,
                                  timeout=10)
            journey.append(result.json()['stations'][0]['name'])
    except KeyError:
        _LOGGER.exception(
            "Unable to determine stations. "
            "Check your settings and/or the availability of opendata.ch")
        return False

    dev = []
    data = PublicTransportData(journey)
    dev.append(SwissPublicTransportSensor(data, journey))
    add_devices(dev)


# pylint: disable=too-few-public-methods
class SwissPublicTransportSensor(Entity):
    """Implementation of an Swiss public transport sensor."""

    def __init__(self, data, journey):
        """Initialize the sensor."""
        self.data = data
        self._name = 'Next Departure'
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
                    ':'.join(str(self._times[2]).split(':')[:2]))
            }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from opendata.ch and update the states."""
        self.data.update()
        self._times = self.data.times
        try:
            self._state = self._times[0]
        except TypeError:
            pass


# pylint: disable=too-few-public-methods
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
            timeout=30)
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
