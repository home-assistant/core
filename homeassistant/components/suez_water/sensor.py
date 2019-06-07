"""Sensor for Suez Water Consumption data."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, VOLUME_LITERS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
CONF_COUNTER_ID = 'counter_id'

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=12)
SCAN_INTERVAL = timedelta(minutes=720)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_COUNTER_ID): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sensor platform."""
    from pysuez.client import PySuezError
    from pysuez import SuezClient

    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)
    counter_id = config.get(CONF_COUNTER_ID)

    try:
        client = SuezClient(
            username, password, counter_id)
        test = client.check_credentials()

        if test:
            _LOGGER.warning("Username and password OK")
            add_devices([SuezHAClient(username, password, counter_id)], True)
        else:
            _LOGGER.warning("Wrong username and/or password")

    except PySuezError:
        _LOGGER.warning("Error creatin a Suez Client")
        return False


class SuezHAClient(Entity):
    """Representation of a Sensor."""

    def __init__(self, username, password, counter_id):
        """Initialize the data object."""
        self._name = "Suez Water Client"
        self._username = username
        self._password = password
        self._counter_id = counter_id
        self._attributes = {}
        self.success = False
        self._state = 0
        self._icon = 'mdi:water-pump'
        self.client = None

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
        """Return the unit of measurement."""
        return VOLUME_LITERS

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    def _fetch_data(self):
        """Fetch latest data from Suez."""
        from pysuez.client import PySuezError
        from pysuez import SuezClient

        try:
            self.client = SuezClient(
                self._username, self._password, self._counter_id)
            self.client.update()

            self._state = self.client.state
            self._attributes = self.client.attributes
            self.success = True

        except PySuezError:
            _LOGGER.warning("Unable to fetch data")
            return False

        return True

    def update(self):
        """Return the latest collected data from Linky."""
        self._fetch_data()
        if not self.success:
            return
        _LOGGER.debug(
            "Suez data state is: %s, and the success is %s",
            self._state, self.success)
