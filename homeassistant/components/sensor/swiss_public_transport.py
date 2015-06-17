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
from requests import get

from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://transport.opendata.ch/v1/'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the Swiss public transport sensor. """

    # journal contains [0] Station ID start, [1] Station ID destination
    # [2] Station name start, and [3] Station name destination
    journey = [config.get('from'), config.get('to')]
    try:
        for location in [config.get('from', None), config.get('to', None)]:
            # transport.opendata.ch doesn't play nice with requests.Session
            result = get(_RESOURCE + 'locations?query=%s' % location)
            journey.append(result.json()['stations'][0]['name'])
    except KeyError:
        _LOGGER.exception(
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
        self._name = '{}-{}'.format(journey[2], journey[3])
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
        try:
            self._state = ', '.join(times)
        except TypeError:
            pass


# pylint: disable=too-few-public-methods
class PublicTransportData(object):
    """ Class for handling the data retrieval. """

    def __init__(self, journey):
        self.start = journey[0]
        self.destination = journey[1]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from opendata.ch. """

        response = get(
            _RESOURCE +
            'connections?' +
            'from=' + self.start + '&' +
            'to=' + self.destination + '&' +
            'fields[]=connections/from/departureTimestamp/&' +
            'fields[]=connections/')

        connections = response.json()['connections'][:2]

        try:
            return [
                dt_util.datetime_to_time_str(
                    dt_util.as_local(dt_util.utc_from_timestamp(
                        item['from']['departureTimestamp']))
                )
                for item in connections
            ]
        except KeyError:
            return ['n/a']
