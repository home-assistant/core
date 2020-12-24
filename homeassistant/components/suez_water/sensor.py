"""Sensor for Suez Water Consumption data."""
from datetime import timedelta
import logging

from pysuez import SuezClient
from pysuez.client import PySuezError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, VOLUME_LITERS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
CONF_COUNTER_ID = "counter_id"

SCAN_INTERVAL = timedelta(hours=12)

COMPONENT_ICON = "mdi:water-pump"
COMPONENT_NAME = "Suez Water Client"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_COUNTER_ID): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    counter_id = config[CONF_COUNTER_ID]
    try:
        client = SuezClient(username, password, counter_id)

        if not client.check_credentials():
            _LOGGER.warning("Wrong username and/or password")
            return

    except PySuezError:
        _LOGGER.warning("Unable to create Suez Client")
        return

    add_entities([SuezSensor(client)], True)


class SuezSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, client):
        """Initialize the data object."""
        self._attributes = {}
        self._state = None
        self._available = None
        self.client = client

    @property
    def name(self):
        """Return the name of the sensor."""
        return COMPONENT_NAME

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return VOLUME_LITERS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return COMPONENT_ICON

    def _fetch_data(self):
        """Fetch latest data from Suez."""
        try:
            self.client.update()
            # _state holds the volume of consumed water during previous day
            self._state = self.client.state
            self._available = True
            self._attributes["attribution"] = self.client.attributes["attribution"]
            self._attributes["this_month_consumption"] = {}
            for item in self.client.attributes["thisMonthConsumption"]:
                self._attributes["this_month_consumption"][
                    item
                ] = self.client.attributes["thisMonthConsumption"][item]
            self._attributes["previous_month_consumption"] = {}
            for item in self.client.attributes["previousMonthConsumption"]:
                self._attributes["previous_month_consumption"][
                    item
                ] = self.client.attributes["previousMonthConsumption"][item]
            self._attributes["highest_monthly_consumption"] = self.client.attributes[
                "highestMonthlyConsumption"
            ]
            self._attributes["last_year_overall"] = self.client.attributes[
                "lastYearOverAll"
            ]
            self._attributes["this_year_overall"] = self.client.attributes[
                "thisYearOverAll"
            ]
            self._attributes["history"] = {}
            for item in self.client.attributes["history"]:
                self._attributes["history"][item] = self.client.attributes["history"][
                    item
                ]

        except PySuezError:
            self._available = False
            _LOGGER.warning("Unable to fetch data")

    def update(self):
        """Return the latest collected data from Linky."""
        self._fetch_data()
        _LOGGER.debug("Suez data state is: %s", self._state)
