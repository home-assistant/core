"""
Support for Dublin RTPI information from data.smartdublin.ie.

For more info on the API see :
https://data.gov.ie/dataset/real-time-passenger-information-rtpi-for-dublin-bus-bus-eireann-luas-and-irish-rail/resource/4b9f2c4f-6bf5-4958-a43a-f12dab04cf61

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dublin_public_transport/
"""
from datetime import timedelta
import logging

from pydublinbus import APIError, DublinBusRTPI
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, TIME_MINUTES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = "stop_id"
ATTR_DUE_IN = "due_in"
ATTR_ROUTE = "route"
ATTR_TIMETABLE = "timetable"

ATTRIBUTION = "Data provided by data.smartdublin.ie"

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dublin public transport sensor."""
    name = config[CONF_NAME]
    stop = config[CONF_STOP_ID]
    route = config[CONF_ROUTE]

    mybus = DublinBusRTPI(stop, route)
    mybus_data = PublicTransportData(mybus)
    add_entities([DublinPublicTransportSensor(mybus_data, mybus, name)], True)


class DublinPublicTransportSensor(Entity):
    """Implementation of an Dublin public transport sensor."""

    def __init__(self, mybus_data, mybus, name):
        """Initialize the sensor."""
        self.mybus_data = mybus_data
        self._name = name
        self._stop = mybus.stopid
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
                ATTR_STOP_ID: self._stop,
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_TIMETABLE: self._times,
                ATTR_ATTRIBUTION: ATTRIBUTION,
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
        """Get the latest data and update the states."""
        self.mybus_data.update()
        self._times = self.mybus_data.info
        self._state = self._times[0][ATTR_DUE_IN]


class PublicTransportData:
    """The Class for handling the data retrieval."""

    def __init__(self, mybus):
        """Initialize the data object."""
        self.mybus = mybus
        self.info = [{ATTR_DUE_IN: "n/a", ATTR_ROUTE: self.mybus.route}]

    def update(self):
        """Get the latest data from the api."""
        try:
            timetable = self.mybus.bus_timetable()
        except APIError:
            _LOGGER.warning("Could not update the dublin bus data")
            return

        self.info = []

        if not timetable:
            self.info = [{ATTR_DUE_IN: "n/a", ATTR_ROUTE: self.mybus.route}]
        else:
            for item in timetable:
                due_in = item.get("due_in")
                route = item.get("route")
                bus_data = {
                    ATTR_DUE_IN: due_in,
                    ATTR_ROUTE: route,
                }
                self.info.append(bus_data)
