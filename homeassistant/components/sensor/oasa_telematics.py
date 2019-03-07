"""
Support for OASA Telematics from telematics.oasa.gr.

Real-time Information for Buses and Trolleys
For more info on the API see:
https://oasa-telematics-api.readthedocs.io/en/latest/
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.oasa_telematics/
"""
import logging
from datetime import timedelta
from operator import itemgetter

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['oasatelematics==0.1']
_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = 'Stop ID'
ATTR_STOP_NAME = 'Stop Name'
ATTR_ROUTE_ID = 'Route ID'
ATTR_ROUTE_NAME = 'Route Name'
ATTR_DUE_IN = 'Due in'
ATTR_NEXT_ARRIVAL = 'Next arrival'

ATTRIBUTION = "Data retrieved from telematics.oasa.gr"

CONF_STOP_ID = 'stop_id'
CONF_ROUTE_ID = 'route_id'

DEFAULT_NAME = 'OASA Telematics'
ICON = 'mdi:bus'

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Required(CONF_ROUTE_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the OASA Telematics sensor."""
    name = config[CONF_NAME]
    stop_id = config[CONF_STOP_ID]
    route_id = config.get(CONF_ROUTE_ID)

    data = OASATelematicsData(stop_id, route_id)

    add_devices([OASATelematicsSensor(
        data, stop_id, route_id, name)], True)


class OASATelematicsSensor(Entity):
    """Implementation of the OASA Telematics sensor."""

    def __init__(self, data, stop_id, route_id, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop_id = stop_id
        self._route_id = route_id
        self._name_data = self._times = self._state = None

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
        params = {}
        if self._times is not None:
            next_arrival = None
            if len(self._times) > 1:
                next_arrival = ('{} min'.format(
                    str(self._times[1][ATTR_DUE_IN])))
            params.update({
                ATTR_DUE_IN: str(self._times[0][ATTR_DUE_IN]),
                ATTR_ROUTE_ID: self._times[0][ATTR_ROUTE_ID],
                ATTR_STOP_ID: self._stop_id,
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_NEXT_ARRIVAL: next_arrival
            })
        params.update({
            ATTR_ROUTE_NAME: self._name_data[ATTR_ROUTE_NAME],
            ATTR_STOP_NAME: self._name_data[ATTR_STOP_NAME]
        })
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
        """Get the latest data from OASA API and update the states."""
        self.data.update()
        self._times = self.data.info
        self._name_data = self.data.name_data
        try:
            self._state = self._times[0][ATTR_DUE_IN]
        except TypeError:
            pass


class OASATelematicsData():
    """The class for handling data retrieval."""

    def __init__(self, stop_id, route_id):
        """Initialize the data object."""
        import oasatelematics
        self.stop_id = stop_id
        self.route_id = route_id
        self.info = self.empty_result()
        self.name_data = self.empty_name_data()
        self.oasa_api = oasatelematics

    def empty_result(self):
        """Object returned when no arrivals are found."""
        return [{ATTR_DUE_IN: 'n/a',
                 ATTR_ROUTE_ID: self.route_id}]

    @staticmethod
    def empty_name_data():
        """Object returned when no stop/route name data are found."""
        return [{ATTR_STOP_NAME: 'n/a',
                 ATTR_ROUTE_NAME: 'n/a'}]

    def get_route_name(self):
        """Get the route name from the API."""
        try:
            route = self.oasa_api.getRouteName(self.route_id)
            if route:
                return route[0].get('route_departure_eng')
        except TypeError:
            _LOGGER.debug("Cannot get route name from OASA API")
        return 'n/a'

    def get_stop_name(self):
        """Get the stop name from the API."""
        try:
            name_data = self.oasa_api.getStopNameAndXY(self.stop_id)
            if name_data:
                return name_data[0].get('stop_descr_matrix_eng')
        except TypeError:
            _LOGGER.debug("Cannot get  stop name from OASA API")
        return 'n/a'

    def update(self):
        """Get the latest arrival data from telematics.oasa.gr API."""
        route = self.get_route_name()
        stop_name = self.get_stop_name()

        self.name_data = {ATTR_ROUTE_NAME: route,
                          ATTR_STOP_NAME: stop_name}

        self.info = []

        results = self.oasa_api.getStopArrivals(self.stop_id)

        if not results:
            self.info = self.empty_result()
            return

        # Parse results
        results = [r for r in results if r.get('route_code') in self.route_id]

        for result in results:
            due_in_minutes = result.get('btime2')

            if due_in_minutes is not None:
                arrival_data = {ATTR_DUE_IN: due_in_minutes,
                                ATTR_ROUTE_ID: self.route_id}
                self.info.append(arrival_data)

        if not self.info:
            _LOGGER.debug("No arrivals with given parameters")
            self.info = self.empty_result()

        # Sort the data by time
        self.info = sorted(self.info, key=itemgetter(ATTR_DUE_IN))
