"""Support for Bizkaibus, Biscay (Basque Country, Spain) Bus service."""

import logging

from bizkaibus.bizkaibus import BizkaibusData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, TIME_MINUTES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_DUE_IN = "Due in"

CONF_STOP_ID = "stopid"
CONF_ROUTE = "route"

DEFAULT_NAME = "Next bus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Required(CONF_ROUTE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Bizkaibus public transport sensor."""
    name = config[CONF_NAME]
    stop = config[CONF_STOP_ID]
    route = config[CONF_ROUTE]

    data = Bizkaibus(stop, route)
    add_entities([BizkaibusSensor(data, stop, route, name)], True)


class BizkaibusSensor(Entity):
    """The class for handling the data."""

    def __init__(self, data, stop, route, name):
        """Initialize the sensor."""
        self.data = data
        self.stop = stop
        self.route = route
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return TIME_MINUTES

    def update(self):
        """Get the latest data from the webservice."""
        self.data.update()
        try:
            self._state = self.data.info[0][ATTR_DUE_IN]
        except TypeError:
            pass


class Bizkaibus:
    """The class for handling the data retrieval."""

    def __init__(self, stop, route):
        """Initialize the data object."""
        self.stop = stop
        self.route = route
        self.info = None

    def update(self):
        """Retrieve the information from API."""
        bridge = BizkaibusData(self.stop, self.route)
        bridge.getNextBus()
        self.info = bridge.info
