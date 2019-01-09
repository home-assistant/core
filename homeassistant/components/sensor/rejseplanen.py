"""
Support for Rejseplanen information from rejseplanen.dk

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rejseplanen/
"""
import logging
from datetime import timedelta, datetime
from operator import itemgetter

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://xmlopen.rejseplanen.dk/bin/rest.exe/departureBoard'

ATTR_STOP_ID = 'Stop ID'
ATTR_STOP_NAME = 'Stop'
ATTR_ROUTE = 'Route'
ATTR_TYPE = 'Type'
ATTR_DIRECTION = "Direction"
ATTR_DUE_IN = 'Due in'
ATTR_DUE_AT = 'Due at'
ATTR_NEXT_UP = 'Later departure'

CONF_ATTRIBUTION = "Data provided by rejseplanen.dk"
CONF_STOP_ID = 'stop_id'
CONF_ROUTE = 'route'
CONF_DIRECTION = 'direction'
CONF_DEPARTURE_TYPE = 'departure_type'

DEFAULT_NAME = 'Next departure'
ICON = 'mdi:bus'

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ROUTE, default=[]):
        vol.All(cv.ensure_list, vol.Length(min=0)),
    vol.Optional(CONF_DIRECTION, default=[]):
        vol.All(cv.ensure_list, vol.Length(min=0)),
    vol.Optional(CONF_DEPARTURE_TYPE, default=[]):
        vol.All(cv.ensure_list, vol.Length(min=0))
})


def due_in_minutes(timestamp):
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format day/month/year hour/minute/second
    """
    diff = datetime.strptime(
        timestamp, "%d.%m.%y %H:%M") - dt_util.now().replace(tzinfo=None)

    return int(diff.total_seconds() / 60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Rejseplanen transport sensor."""
    name = config.get(CONF_NAME)
    stop_id = config.get(CONF_STOP_ID)
    route = config.get(CONF_ROUTE)
    direction = config.get(CONF_DIRECTION)
    departure_type = config.get(CONF_DEPARTURE_TYPE)

    data = PublicTransportData(stop_id, route, direction, departure_type)
    add_devices([RejseplanenTransportSensor(data, stop_id, route, direction, name)], True)


class RejseplanenTransportSensor(Entity):
    """Implementation of Rejseplanen transport sensor."""

    def __init__(self, data, stop_id, route, direction, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop_id = stop_id
        self._route = route
        self._direction = direction
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
            next_up = "None"
            if len(self._times) > 1:
                next_up = self._times[1][ATTR_ROUTE] + " towards " + self._times[1][ATTR_DIRECTION] + " in "
                next_up += str(self._times[1][ATTR_DUE_IN])
                next_up += " from " + self._times[1][ATTR_STOP_NAME]

            return {
                ATTR_DUE_IN: str(self._times[0][ATTR_DUE_IN]),
                ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
                ATTR_TYPE: self._times[0][ATTR_TYPE],
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_DIRECTION: self._times[0][ATTR_DIRECTION],
                ATTR_STOP_NAME: self._times[0][ATTR_STOP_NAME],
                ATTR_STOP_ID: self._stop_id,
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_NEXT_UP: next_up
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
        """Get the latest data from rejseplanen.dk and update the states."""
        self.data.update()
        self._times = self.data.info
        try:
            self._state = self._times[0][ATTR_DUE_IN]
        except TypeError:
            pass


class PublicTransportData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, stop_id, route, direction, departure_type):
        """Initialize the data object."""
        self.stop_id = stop_id
        self.route = route
        self.direction = direction
        self.departure_type = departure_type
        self.info = [{ATTR_DUE_IN: 'n/a',
                      ATTR_DUE_AT: 'n/a',
                      ATTR_TYPE: 'n/a',
                      ATTR_ROUTE: self.route,
                      ATTR_DIRECTION: 'n/a',
                      ATTR_STOP_NAME: 'n/a'}]

    def update(self):
        """Get the latest data from rejseplanen."""
        params = {}
        params['id'] = self.stop_id
        # Can't specify route and direction in query for rejseplanen, will have to filter results
        params['format'] = 'json'

        response = requests.get(_RESOURCE, params, timeout=10)

        if response.status_code != 200:
            self.info = [{ATTR_DUE_IN: 'n/a',
                          ATTR_DUE_AT: 'n/a',
                          ATTR_TYPE: 'n/a',
                          ATTR_ROUTE: self.route,
                          ATTR_DIRECTION: 'n/a',
                          ATTR_STOP_NAME: 'n/a'}]
            return

        result = response.json()['DepartureBoard']

        # This key is present on error
        if 'error' in result:
            self.info = [{ATTR_DUE_IN: 'n/a',
                          ATTR_DUE_AT: 'n/a',
                          ATTR_TYPE: 'n/a',
                          ATTR_ROUTE: self.route,
                          ATTR_DIRECTION: 'n/a',
                          ATTR_STOP_NAME: 'n/a'}]
            return

        self.info = []
        for item in result['Departure']:
            departure_type = item.get('type')
            stop = item.get('stop')
            route = item.get('name')
            direction = item.get('direction')

            # Make sure it's not cancelled
            cancelled = item.get('cancelled')
            if cancelled is not None:
                continue

            # Filter based on route
            if self.route:
                #if route != self.route:
                if route not in self.route:
                    continue

            # Filter based on direction
            if self.direction:
                if direction not in self.direction:
                    continue
            
            # Filter based on type
            if self.departure_type:
                if departure_type not in self.departure_type:
                    continue

            # The fields rtDate and rtTime have information about delays. They are however not always present.
            due_at_date = item.get('rtDate')
            due_at_time = item.get('rtTime')

            if due_at_date is None:
                due_at_date = item.get('date') # Scheduled date
            if due_at_time is None:
                due_at_time = item.get('time') # Scheduled time

            if due_at_date is not None and due_at_time is not None and route is not None:
                due_at = due_at_date + " " + due_at_time

                departure_data = {ATTR_DUE_IN: due_in_minutes(due_at),
                            ATTR_DUE_AT: due_at,
                            ATTR_TYPE: departure_type,
                            ATTR_ROUTE: route,
                            ATTR_DIRECTION: direction,
                            ATTR_STOP_NAME: stop}
                self.info.append(departure_data)

        if not self.info:
            self.info = [{ATTR_DUE_IN: 'n/a',
                          ATTR_DUE_AT: 'n/a',
                          ATTR_TYPE: 'n/a',
                          ATTR_ROUTE: self.route,
                          ATTR_DIRECTION: 'n/a',
                          ATTR_STOP_NAME: 'n/a'}]

        # Sort the data by time
        self.info = sorted(self.info, key=itemgetter(ATTR_DUE_IN))