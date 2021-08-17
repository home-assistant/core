"""Sensor for displaying the number of result on Shodan.io."""
from datetime import timedelta
import logging

import shodan
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY, CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Shodan"

CONF_QUERY = "query"

DEFAULT_NAME = "Shodan Sensor"

ICON = "mdi:tooltip-text"

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_QUERY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Shodan sensor."""
    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)
    query = config.get(CONF_QUERY)

    data = ShodanData(shodan.Shodan(api_key), query)
    try:
        data.update()
    except shodan.exception.APIError as error:
        _LOGGER.warning("Unable to connect to Shodan.io: %s", error)
        return False

    add_entities([ShodanSensor(data, name)], True)


class ShodanSensor(SensorEntity):
    """Representation of the Shodan sensor."""

    def __init__(self, data, name):
        """Initialize the Shodan sensor."""
        self.data = data
        self._name = name
        self._state = None
        self._unit_of_measurement = "Hits"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._state = self.data.details["total"]


class ShodanData:
    """Get the latest data and update the states."""

    def __init__(self, api, query):
        """Initialize the data object."""
        self._api = api
        self._query = query
        self.details = None

    def update(self):
        """Get the latest data from shodan.io."""
        self.details = self._api.count(self._query)
