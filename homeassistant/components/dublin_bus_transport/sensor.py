"""
Support for Dublin RTPI information from data.dublinked.ie.

For more info on the API see :
https://data.gov.ie/dataset/real-time-passenger-information-rtpi-for-dublin-bus-bus-eireann-luas-and-irish-rail/resource/4b9f2c4f-6bf5-4958-a43a-f12dab04cf61
"""
from contextlib import suppress
from datetime import datetime, timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, HTTP_OK, TIME_MINUTES
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_RESOURCE = "https://data.dublinked.ie/cgi-bin/rtpi/realtimebusinformation"

ATTR_STOP_ID = "Stop ID"
ATTR_ROUTE = "Route"
ATTR_DUE_IN = "Due in"
ATTR_DUE_AT = "Due at"
ATTR_NEXT_UP = "Later Bus"

ATTRIBUTION = "Data provided by data.dublinked.ie"

CONF_STOP_ID = "stopid"
CONF_ROUTE = "route"

DEFAULT_NAME = "Next Bus"
ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(minutes=1)
TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROUTE, default=""): cv.string,
    }
)


def due_in_minutes(timestamp):
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format day/month/year hour/minute/second
    """
    diff = datetime.strptime(timestamp, "%d/%m/%Y %H:%M:%S") - dt_util.now().replace(
        tzinfo=None
    )

    return str(int(diff.total_seconds() / 60))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dublin public transport sensor."""
    name = config[CONF_NAME]
    stop = config[CONF_STOP_ID]
    route = config[CONF_ROUTE]

    data = PublicTransportData(stop, route)
    add_entities([DublinPublicTransportSensor(data, stop, route, name)], True)


class DublinPublicTransportSensor(SensorEntity):
    """Implementation of an Dublin public transport sensor."""

    def __init__(self, data, stop, route, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop = stop
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
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._times is not None:
            next_up = "None"
            if len(self._times) > 1:
                next_up = f"{self._times[1][ATTR_ROUTE]} in "
                next_up += self._times[1][ATTR_DUE_IN]

            return {
                ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
                ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
                ATTR_STOP_ID: self._stop,
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_NEXT_UP: next_up,
            }

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TIME_MINUTES

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from opendata.ch and update the states."""
        self.data.update()
        self._times = self.data.info
        with suppress(TypeError):
            self._state = self._times[0][ATTR_DUE_IN]


class PublicTransportData:
    """The Class for handling the data retrieval."""

    def __init__(self, stop, route):
        """Initialize the data object."""
        self.stop = stop
        self.route = route
        self.info = [{ATTR_DUE_AT: "n/a", ATTR_ROUTE: self.route, ATTR_DUE_IN: "n/a"}]

    def update(self):
        """Get the latest data from opendata.ch."""
        params = {}
        params["stopid"] = self.stop

        if self.route:
            params["routeid"] = self.route

        params["maxresults"] = 2
        params["format"] = "json"

        response = requests.get(_RESOURCE, params, timeout=10)

        if response.status_code != HTTP_OK:
            self.info = [
                {ATTR_DUE_AT: "n/a", ATTR_ROUTE: self.route, ATTR_DUE_IN: "n/a"}
            ]
            return

        result = response.json()

        if str(result["errorcode"]) != "0":
            self.info = [
                {ATTR_DUE_AT: "n/a", ATTR_ROUTE: self.route, ATTR_DUE_IN: "n/a"}
            ]
            return

        self.info = []
        for item in result["results"]:
            due_at = item.get("departuredatetime")
            route = item.get("route")
            if due_at is not None and route is not None:
                bus_data = {
                    ATTR_DUE_AT: due_at,
                    ATTR_ROUTE: route,
                    ATTR_DUE_IN: due_in_minutes(due_at),
                }
                self.info.append(bus_data)

        if not self.info:
            self.info = [
                {ATTR_DUE_AT: "n/a", ATTR_ROUTE: self.route, ATTR_DUE_IN: "n/a"}
            ]
