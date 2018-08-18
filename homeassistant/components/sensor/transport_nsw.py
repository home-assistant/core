"""
Transport NSW sensor to query next leave event for a specified stop (bus, train or ferry).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import logging
from datetime import timedelta, datetime

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = 'stopid'
ATTR_ROUTE = 'route'
ATTR_DUE_IN = 'due'
ATTR_DELAY = 'delay'
ATTR_REALTIME = 'realtime'

CONF_ATTRIBUTION = "Data provided by Transport NSW"
CONF_STOP_ID = 'stopid'
CONF_ROUTE = 'route'
CONF_APIKEY = 'apikey'

DEFAULT_NAME = "Next Bus"
ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(minutes=1)
TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Required(CONF_APIKEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ROUTE, default=""): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Transport NSW sensor."""
    name = config.get(CONF_NAME)
    stopid = config.get(CONF_STOP_ID)
    route = config.get(CONF_ROUTE)
    apikey = config.get(CONF_APIKEY)

    data = PublicTransportData(stopid, route, apikey)
    add_devices([TransportNSWSensor(data, stopid, route, name)], True)


class TransportNSWSensor(Entity):
    """Implementation of an Transport NSW sensor."""

    def __init__(self, data, stopid, route, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stopid = stopid
        self._route = route
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
                ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
                ATTR_STOP_ID: self._stopid,
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_DELAY: self._times[0][ATTR_DELAY],
                ATTR_REALTIME: self._times[0][ATTR_REALTIME],
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION
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
        """Get the latest data from Transport NSW and update the states."""
        self.data.update()
        self._times = self.data.info
        try:
            self._state = self._times[0][ATTR_DUE_IN]
        except TypeError:
            pass


class PublicTransportData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, stopid, route, apikey):
        """Initialize the data object."""
        self.stopid = stopid
        self.route = route
        self.apikey = apikey
        self.info = [{ATTR_ROUTE: self.route,
                      ATTR_DUE_IN: 'n/a',
                      ATTR_DELAY: 'n/a',
                      ATTR_REALTIME: 'n/a'}]

    def update(self):
        """Get the latest data from Transport NSW."""

        url = ("https://api.transport.nsw.gov.au/v1/tp/departure_mon?"
               "outputFormat=rapidJSON&"
               "coordOutputFormat=EPSG%3A4326&"
               "mode=direct&"
               "type_dm=stop&"
               "name_dm="+self.stopid+"&"
               "departureMonitorMacro=true&"
               "TfNSWDM=true&"
               "version=10.2.1.42")
        auth = 'apikey ' + self.apikey
        header = {'Accept': 'application/json',
                  'Authorization': auth}
        response = requests.get(url, headers=header, timeout=10)

        _LOGGER.debug(response)

        # No valid request, set to default
        if response.status_code != 200:
            _LOGGER.error(response.status_code)
            self.info = [{ATTR_ROUTE: self.route,
                          ATTR_DUE_IN: 'n/a',
                          ATTR_DELAY: 'n/a',
                          ATTR_REALTIME: 'n/a'}]
            return

        # Parse the result as a JSON object
        result = response.json()

        # No stop events for the query
        if len(result['stopEvents']) <= 0:
            _LOGGER.error("No stop events for this query")
            self.info = [{ATTR_ROUTE: self.route,
                          ATTR_DUE_IN: 'n/a',
                          ATTR_DELAY: 'n/a',
                          ATTR_REALTIME: 'n/a'}]
            return

        # Set timestamp format and variables
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        maxresults = 3
        monitor = []

        if self.route != '':
            # Find any bus leaving next
            for i in range(len(result['stopEvents'])):
                number = result['stopEvents'][i]['transportation']['number']
                if number == self.route:
                    planned = datetime.strptime(
                        result['stopEvents'][i]['departureTimePlanned'],
                        fmt)

                    realtime = 'n'
                    estimated = planned
                    delay = 0
                    if 'isRealtimeControlled' in result['stopEvents'][i]:
                        realtime = 'y'
                        estimated = datetime.strptime(
                            result['stopEvents'][i]['departureTimeEstimated'],
                            fmt)

                    if estimated > datetime.utcnow():
                        due = round((estimated - datetime.utcnow()).seconds/60)
                        if estimated >= planned:
                            delay = round((estimated-planned).seconds/60)
                        else:
                            delay = round((planned-estimated).seconds/60) * -1

                        monitor.append(
                            [number, due, delay, planned, estimated, realtime])

                    if len(monitor) >= maxresults:
                        # We found enough results, lets stop
                        break
        else:
            # Find the next stop events
            for i in range(0, maxresults):
                number = result['stopEvents'][i]['transportation']['number']

                planned = datetime.strptime(
                    result['stopEvents'][i]['departureTimePlanned'],
                    fmt)

                realtime = 'n'
                estimated = planned
                delay = 0
                if 'isRealtimeControlled' in result['stopEvents'][i]:
                    realtime = 'y'
                    estimated = datetime.strptime(
                        result['stopEvents'][i]['departureTimeEstimated'],
                        fmt)

                if estimated > datetime.utcnow():
                    due = round((estimated - datetime.utcnow()).seconds/60)
                    if estimated >= planned:
                        delay = round((estimated-planned).seconds/60)
                    else:
                        delay = round((planned-estimated).seconds/60) * -1

                    monitor.append(
                        [number, due, delay, planned, estimated, realtime])

        if len(monitor) > 0:
            self.info = [{ATTR_ROUTE: monitor[0][0],
                          ATTR_DUE_IN: monitor[0][1],
                          ATTR_DELAY: monitor[0][2],
                          ATTR_REALTIME: monitor[0][5]}]
            return
        else:
            # _LOGGER.error("No stop events for this route.")
            self.info = [{ATTR_ROUTE: self.route,
                          ATTR_DUE_IN: 'n/a',
                          ATTR_DELAY: 'n/a',
                          ATTR_REALTIME: 'n/a'}]
            return
