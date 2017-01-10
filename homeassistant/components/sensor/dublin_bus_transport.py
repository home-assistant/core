"""Support for Dublin RTPI information from data.dublinked.ie.

For more info on the API see :
https://data.gov.ie/dataset/real-time-passenger-information-rtpi-for-dublin-bus-bus-eireann-luas-and-irish-rail/resource/4b9f2c4f-6bf5-4958-a43a-f12dab04cf61

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dublin_public_transport/

Example Configuration:

sensor:
  - platform: dublin_bus_transport
    # stopid available from Dublin Bus
    stopid: 334
    # Optional bust route
    route: 140
    # Optional name
    name: 140 at Quays
"""
import logging
from datetime import timedelta, datetime

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://data.dublinked.ie/cgi-bin/rtpi/realtimebusinformation'

ATTR_STOP_ID = "Stop ID"
ATTR_ROUTE = "Route"
ATTR_DUE_IN = "Due in"
ATTR_DUE_AT = "Due at"
ATTR_NEXT_UP = "Later Bus"

CONF_ATTRIBUTION = "Data provided by data.dublinked.ie"
CONF_STOP_ID = 'stopid'
CONF_ROUTE = 'route'

DEFAULT_NAME = 'Next Bus'
ICON = 'mdi:bus'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ROUTE, default=""): cv.string,
})


def time_in_minutes(diff):
    """Get the time in minutes for a timedelta."""
    return str(int(diff.total_seconds() / 60))


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the Dublin public transport sensor."""
    name = config.get(CONF_NAME)
    stop = config.get(CONF_STOP_ID)
    route = config.get(CONF_ROUTE)

    data = PublicTransportData(stop, route)
    add_devices([DublinPublicTransportSensor(data, stop, route, name)])


class DublinPublicTransportSensor(Entity):
    """Implementation of an Dublin public transport sensor."""

    def __init__(self, data, stop, route, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop = stop
        self._route = route
        self.update()
        self._unit_of_measurement = "min"

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
            next_up = "None"
            if len(self._times) > 1:
                next_up = self._times[1][ATTR_ROUTE] + " in "
                next_up += self._times[1][ATTR_DUE_IN]

            return {
                ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
                ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
                ATTR_STOP_ID: self._stop,
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_NEXT_UP: next_up
            }

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from opendata.ch and update the states."""
        self.data.update()
        self._times = self.data.info
        try:
            self._state = self._times[0][ATTR_DUE_IN]
        except TypeError:
            pass


class PublicTransportData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, stop, route):
        """Initialize the data object."""
        self.stop = stop
        self.route = route
        self.info = [{ATTR_DUE_AT: 'n/a',
                      ATTR_ROUTE: self.route,
                      ATTR_DUE_IN: 'n/a'}]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from opendata.ch."""
        params = {}
        params['stopid'] = self.stop

        if len(self.route) > 0:
            params['routeid'] = self.route

        params['maxresults'] = 2
        params['format'] = 'json'

        response = requests.get(
            _RESOURCE,
            params,
            timeout=10)

        if response.status_code != 200:
            self.info = [{ATTR_DUE_AT: 'n/a',
                          ATTR_ROUTE: self.route,
                          ATTR_DUE_IN: 'n/a'}]
            return

        result = response.json()

        if str(result['errorcode']) != '0':
            self.info = [{ATTR_DUE_AT: 'n/a',
                          ATTR_ROUTE: self.route,
                          ATTR_DUE_IN: 'n/a'}]
            return

        try:
            self.info = [
                {ATTR_DUE_AT: item['departuredatetime'],
                 ATTR_ROUTE: item['route'],
                 ATTR_DUE_IN: time_in_minutes(
                     dt_util.as_local(
                         dt_util.utc_from_timestamp(
                             dt_util.as_timestamp(
                                 datetime.strptime(item['departuredatetime'],
                                                   "%d/%m/%Y %H:%M:%S")))) -
                     dt_util.as_local(dt_util.utcnow()))}
                for item in result['results']
            ]

        except KeyError:
            self.info = [{ATTR_DUE_AT: 'n/a',
                          ATTR_ROUTE: self.route,
                          ATTR_DUE_IN: 'n/a'}]
