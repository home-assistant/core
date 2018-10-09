"""
Real-time information about public transport departures in Norway.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.entur_public_transport/
"""
from datetime import datetime, timedelta
import logging
from string import Template

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://api.entur.org/journeyplanner/2.0/index/graphql'
_GRAPHQL_STOP_TEMPLATE = """
  stopPlaces(ids: [$stops]) {
    id
    name
    estimatedCalls(
        startTime: \"$time\",
        timeRange: 72100,
        numberOfDepartures: 2) {
      realtime
      aimedArrivalTime
      aimedDepartureTime
      expectedArrivalTime
      expectedDepartureTime
      requestStop
      notices {
        text
      }
      destinationDisplay {
        frontText
      }
      serviceJourney {
        journeyPattern {
          line {
            id
            name
            transportMode
          }
        }
      }
    }
  }
"""
_GRAPHQL_QUAY_TEMPLATE = """
  quays(ids:[$quays]) {
    id
    name
    estimatedCalls(
        startTime: \"$time\",
        timeRange: 72100,
        numberOfDepartures: 2) {
      realtime
      aimedArrivalTime
      aimedDepartureTime
      expectedArrivalTime
      expectedDepartureTime
      requestStop
      notices {
        text
      }
      destinationDisplay {
        frontText
      }
      serviceJourney {
        journeyPattern {
          line {
            id
            name
            transportMode
          }
        }
      }
    }
  }
"""

ATTR_STOP_ID = 'Stop ID'

ATTR_ROUTE = 'Route'
ATTR_EXPECTED_IN = 'Due in'
ATTR_EXPECTED_AT = 'Due at'
ATTR_DELAY = 'Delay'
ATTR_REALTIME = 'Real-time'

ATTR_NEXT_UP_ROUTE = 'Next departure route'
ATTR_NEXT_UP_IN = 'Next departure in'
ATTR_NEXT_UP_AT = 'Next departure at'
ATTR_NEXT_UP_DELAY = 'Next departure delay'
ATTR_NEXT_UP_REALTIME = 'Next departure is real-time'

CONF_ATTRIBUTION = "Data provided by entur.org under NLOD."
CONF_STOP_IDS = 'stop_ids'

ICON = 'mdi:bus'

SCAN_INTERVAL = timedelta(minutes=1)
TIME_STR_FORMAT = '%H:%M'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_IDS): vol.All(cv.ensure_list, [cv.string]),
})


def due_in_minutes(timestamp: str) -> str:
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format
    year-month-yearThour:minute:second+timezone
    """
    if timestamp is None:
        return 'Unknown'
    diff = datetime.strptime(
        timestamp, "%Y-%m-%dT%H:%M:%S%z") - dt_util.now()

    return str(int(diff.total_seconds() / 60))


def time_diff_in_minutes(timestamp1: str, timestamp2: str) -> str:
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format
    year-month-yearThour:minute:second+timezone
    """
    if timestamp1 is None:
        return 'Unknown'
    if timestamp2 is None:
        return 'Unknown'

    time1 = datetime.strptime(timestamp1, "%Y-%m-%dT%H:%M:%S%z")
    time2 = datetime.strptime(timestamp2, "%Y-%m-%dT%H:%M:%S%z")
    diff = time1 - time2

    return str(int(diff.total_seconds() / 60))


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the Dublin public transport sensor."""
    stop_ids = config.get(CONF_STOP_IDS)

    stops = [s for s in stop_ids if "StopPlace" in s]
    quays = [s for s in stop_ids if "Quay" in s]

    data = PublicTransportData(stops, quays)
    data.update()
    entities = []
    for item in stop_ids:
        entities.append(EnturPublicTransportSensor(data, item))

    add_entities(entities, True)


class PublicTransportData:
    """The Class for handling the data retrieval."""

    def __init__(self, stops: list, quays: list):
        """Initialize the data object."""
        self.stops = stops
        self.stops_string = "\"" + "\",\"".join(stops) + "\""
        self.quays = quays
        self.quays_string = "\"" + "\",\"".join(quays) + "\""

        self.info = {}
        for item in stops:
            self.info[item] = {ATTR_STOP_ID: 'Unknown',
                               CONF_NAME: item,
                               ATTR_EXPECTED_AT: 'Unknown',
                               ATTR_REALTIME: 'Unknown',
                               ATTR_ROUTE: 'Unknown',
                               ATTR_DELAY: 'Unknown'}
        for item in quays:
            self.info[item] = {ATTR_STOP_ID: 'Unknown',
                               CONF_NAME: item,
                               ATTR_EXPECTED_AT: 'Unknown',
                               ATTR_REALTIME: 'Unknown',
                               ATTR_ROUTE: 'Unknown',
                               ATTR_DELAY: 'Unknown'}

        self.template_string = "{\n"
        if len(self.stops) > 0:
            self.template_string += _GRAPHQL_STOP_TEMPLATE
        if len(self.quays) > 0:
            self.template_string += _GRAPHQL_QUAY_TEMPLATE
        self.template_string += "}"
        self.template = Template(self.template_string)

    @Throttle(SCAN_INTERVAL)
    def update(self) -> None:
        """Get the latest data from api.entur.org."""
        query = self.template.substitute(
            stops=self.stops_string,
            quays=self.quays_string,
            time=datetime.utcnow().strftime("%Y-%m-%dT%XZ"))
        headers = {'ET-Client-Name': 'home-assistant'}
        response = requests.post(
            _RESOURCE,
            json={"query": query},
            timeout=10,
            headers=headers)

        if response.status_code != 200:
            _LOGGER.warning(
                "Got non success http code from entur api: %s",
                response.status_code)
            return

        result = response.json()

        if 'errors' in result:
            _LOGGER.warning(
                "Got error from entur api: %s",
                str(result['errors']))
            return

        if 'stopPlaces' in result['data']:
            for stop in result['data']['stopPlaces']:
                self._process_place(stop)

        if 'quays' in result['data']:
            for quey in result['data']['quays']:
                self._process_place(quey)

    def _process_place(self, place_dict: dict) -> None:
        """Extracts information from place dictionary."""
        place_id = place_dict['id']
        info = {ATTR_STOP_ID: place_id,
                CONF_NAME: place_dict['name']}
        if len(place_dict['estimatedCalls']) > 0:
            call = place_dict['estimatedCalls'][0]
            info[ATTR_EXPECTED_AT] = call['expectedDepartureTime']
            info[ATTR_REALTIME] = call['realtime']
            info[ATTR_ROUTE] = \
                call['serviceJourney']['journeyPattern']['line']['name'] \
                + " " + call['destinationDisplay']['frontText']
            info[ATTR_DELAY] = time_diff_in_minutes(
                call['expectedDepartureTime'],
                call['aimedDepartureTime'])
        if len(place_dict['estimatedCalls']) > 1:
            call = place_dict['estimatedCalls'][1]
            info[ATTR_NEXT_UP_AT] = call['expectedDepartureTime']
            info[ATTR_NEXT_UP_REALTIME] = call['realtime']
            info[ATTR_NEXT_UP_ROUTE] = \
                call['serviceJourney']['journeyPattern']['line']['name'] \
                + " " + call['destinationDisplay']['frontText']
            info[ATTR_NEXT_UP_DELAY] = time_diff_in_minutes(
                call['expectedDepartureTime'],
                call['aimedDepartureTime'])
        self.info[place_id] = info


class EnturPublicTransportSensor(Entity):
    """Implementation of a Entur public transport sensor."""

    def __init__(self, data: PublicTransportData, stop: str):
        """Initialize the sensor."""
        self.data = data
        self._stop = stop
        self._times = {ATTR_STOP_ID: 'Unknown',
                       CONF_NAME: stop,
                       ATTR_EXPECTED_AT: 'Unknown',
                       ATTR_REALTIME: 'Unknown',
                       ATTR_ROUTE: 'Unknown',
                       ATTR_DELAY: 'Unknown'}
        self._state = 'Unknown'
        try:
            self._name = "Entur " + data.info[stop][CONF_NAME] + " Departures"
        except TypeError:
            self._name = stop

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        if self._times is not None:
            return {
                ATTR_STOP_ID: self._stop,

                ATTR_ROUTE: self._times[ATTR_ROUTE],
                ATTR_DELAY: self._times[ATTR_DELAY],
                ATTR_EXPECTED_IN: due_in_minutes(
                    self._times[ATTR_EXPECTED_AT]),
                ATTR_EXPECTED_AT: self._times[ATTR_EXPECTED_AT],
                ATTR_REALTIME: self._times[ATTR_REALTIME],

                ATTR_NEXT_UP_ROUTE: self._times[ATTR_NEXT_UP_ROUTE],
                ATTR_NEXT_UP_DELAY: self._times[ATTR_NEXT_UP_DELAY],
                ATTR_NEXT_UP_IN: due_in_minutes(self._times[ATTR_NEXT_UP_AT]),
                ATTR_NEXT_UP_AT: self._times[ATTR_NEXT_UP_AT],
                ATTR_NEXT_UP_REALTIME: self._times[ATTR_NEXT_UP_REALTIME],

                ATTR_ATTRIBUTION: CONF_ATTRIBUTION
            }

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return 'min'

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return ICON

    def update(self) -> None:
        """Get the latest data and update the states."""
        self.data.update()
        self._times = self.data.info[self._stop]
        try:
            self._state = due_in_minutes(self._times[ATTR_EXPECTED_AT])
        except TypeError:
            pass
