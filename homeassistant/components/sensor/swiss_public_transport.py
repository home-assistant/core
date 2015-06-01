"""
homeassistant.components.sensor.swiss_public_transport
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Swiss public transport sensor will give you the next two departure times
from a given location to another one. This sensor is limited to Switzerland.

Configuration:

To use the Swiss public transport sensor you will need to add something like
the following to your config/configuration.yaml

sensor:
  platform: swiss_public_transport
  from: STATION_ID
  to: STATION_ID

Variables:

from
*Required
Start station/stop of your trip. To search for the ID of the station, use the
an URL like this: http://transport.opendata.ch/v1/locations?query=Wankdorf
to query for the station. If the score is 100 ("score":"100" in the response),
it is a perfect match.

to
*Required
Destination station/stop of the trip. Same procedure as for the start station.

Details for the API : http://transport.opendata.ch
"""
import logging
from datetime import timedelta

from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://transport.opendata.ch/v1/'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the Swiss public transport sensor. """

    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    try:
        # pylint: disable=unused-variable
        from requests import get

    except ImportError:
        _LOGGER.exception(
            "Unable to import requests. "
            "Did you maybe not install the 'Requests' package?")

        return None

    # journal contains [0] Station ID start, [1] Station ID destination
    # [2] Station name start, and [3] Station name destination
    journey = []
    journey.append(config.get('from', None))
    journey.append(config.get('to', None))
    try:
        for location in [config.get('from', None), config.get('to', None)]:
            # transport.opendata.ch doesn't play nice with requests.Session
            result = get(_RESOURCE + 'locations?query=%s' % location)
            journey.append(result.json()['stations'][0]['name'])
    except KeyError:
        _LOGGER.error(
            "Unable to determine stations. "
            "Check your settings and/or the availability of opendata.ch")

        return None

    dev = []
    data = PublicTransportData(journey)
    dev.append(SwissPublicTransportSensor(data, journey))
    add_devices(dev)


# pylint: disable=too-few-public-methods
class SwissPublicTransportSensor(Entity):
    """ Implements an Swiss public transport sensor. """

    def __init__(self, data, journey):
        self.data = data
        self._name = journey[2] + '-' + journey[3]
        self.update()

    @property
    def name(self):
        """ Returns the name. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    # pylint: disable=too-many-branches
    def update(self):
        """ Gets the latest data from opendata.ch and updates the states. """
        times = self.data.update()
        if times is not None:
            self._state = ', '.join(times)


# pylint: disable=too-few-public-methods
class PublicTransportData(object):
    """ Class for handling the data retrieval.  """

    def __init__(self, journey):
        self.times = ['n/a', 'n/a']
        self.start = journey[0]
        self.destination = journey[1]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from opendata.ch. """

        from requests import get

        response = get(
            _RESOURCE +
            'connections?' +
            'from=' + self.start + '&' +
            'to=' + self.destination + '&' +
            'fields[]=connections/from/departureTimestamp/&' +
            'fields[]=connections/')

        try:
            self.times.insert(0, dt_util.timestamp_to_short_time_str(
                response.json()['connections'][0]['from']
                ['departureTimestamp']))
            self.times.insert(1, dt_util.timestamp_to_short_time_str(
                response.json()['connections'][1]['from']
                ['departureTimestamp']))
            return self.times

        except KeyError:
            return self.times
