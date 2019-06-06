"""
Support for Rejseplanen information from rejseplanen.dk.

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rejseplanen/
"""
import logging
from datetime import timedelta, datetime
from operator import itemgetter

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = 'Stop ID'
ATTR_STOP_NAME = 'Stop'
ATTR_ROUTE = 'Route'
ATTR_TYPE = 'Type'
ATTR_DIRECTION = "Direction"
ATTR_DUE_IN = 'Due in'
ATTR_DUE_AT = 'Due at'
ATTR_NEXT_UP = 'Later departure'

ATTRIBUTION = "Data provided by rejseplanen.dk"

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
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DIRECTION, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEPARTURE_TYPE, default=[]):
        vol.All(cv.ensure_list,
                [vol.In(list(['BUS', 'EXB', 'M', 'S', 'REG']))])
})


def due_in_minutes(timestamp):
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format day.month.year hour:minute
    """
    diff = datetime.strptime(
        timestamp, "%d.%m.%y %H:%M") - dt_util.now().replace(tzinfo=None)

    return int(diff.total_seconds() // 60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Rejseplanen transport sensor."""
    name = config[CONF_NAME]
    stop_id = config[CONF_STOP_ID]
    route = config.get(CONF_ROUTE)
    direction = config[CONF_DIRECTION]
    departure_type = config[CONF_DEPARTURE_TYPE]

    data = PublicTransportData(stop_id, route, direction, departure_type)
    add_devices([RejseplanenTransportSensor(
        data, stop_id, route, direction, name)], True)


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
            next_up = None
            if len(self._times) > 1:
                next_up = ('{} towards {} in {} from {}'.format(
                    self._times[1][ATTR_ROUTE],
                    self._times[1][ATTR_DIRECTION],
                    str(self._times[1][ATTR_DUE_IN]),
                    self._times[1][ATTR_STOP_NAME]))
            params = {
                ATTR_DUE_IN: str(self._times[0][ATTR_DUE_IN]),
                ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
                ATTR_TYPE: self._times[0][ATTR_TYPE],
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_DIRECTION: self._times[0][ATTR_DIRECTION],
                ATTR_STOP_NAME: self._times[0][ATTR_STOP_NAME],
                ATTR_STOP_ID: self._stop_id,
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_NEXT_UP: next_up
            }
            return {k: v for k, v in params.items() if v}

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


class PublicTransportData():
    """The Class for handling the data retrieval."""

    def __init__(self, stop_id, route, direction, departure_type):
        """Initialize the data object."""
        self.stop_id = stop_id
        self.route = route
        self.direction = direction
        self.departure_type = departure_type
        self.info = self.empty_result()

    def empty_result(self):
        """Object returned when no departures are found."""
        return [{ATTR_DUE_IN: 'n/a',
                 ATTR_DUE_AT: 'n/a',
                 ATTR_TYPE: 'n/a',
                 ATTR_ROUTE: self.route,
                 ATTR_DIRECTION: 'n/a',
                 ATTR_STOP_NAME: 'n/a'}]

    def update(self):
        """Get the latest data from rejseplanen."""
        import rjpl
        self.info = []

        try:
            results = rjpl.departureBoard(int(self.stop_id), timeout=5)
        except rjpl.rjplAPIError as error:
            _LOGGER.debug("API returned error: %s", error)
            self.info = self.empty_result()
            return
        except (rjpl.rjplConnectionError, rjpl.rjplHTTPError):
            _LOGGER.debug("Error occured while connecting to the API")
            self.info = self.empty_result()
            return

        # Filter result
        results = [d for d in results if 'cancelled' not in d]
        if self.route:
            results = [d for d in results if d['name'] in self.route]
        if self.direction:
            results = [d for d in results if d['direction'] in self.direction]
        if self.departure_type:
            results = [d for d in results if d['type'] in self.departure_type]

        for item in results:
            route = item.get('name')

            due_at_date = item.get('rtDate')
            due_at_time = item.get('rtTime')

            if due_at_date is None:
                due_at_date = item.get('date')  # Scheduled date
            if due_at_time is None:
                due_at_time = item.get('time')  # Scheduled time

            if (due_at_date is not None and
                    due_at_time is not None and
                    route is not None):
                due_at = '{} {}'.format(due_at_date, due_at_time)

                departure_data = {ATTR_DUE_IN: due_in_minutes(due_at),
                                  ATTR_DUE_AT: due_at,
                                  ATTR_TYPE: item.get('type'),
                                  ATTR_ROUTE: route,
                                  ATTR_DIRECTION: item.get('direction'),
                                  ATTR_STOP_NAME: item.get('stop')}
                self.info.append(departure_data)

        if not self.info:
            _LOGGER.debug("No departures with given parameters")
            self.info = self.empty_result()

        # Sort the data by time
        self.info = sorted(self.info, key=itemgetter(ATTR_DUE_IN))
