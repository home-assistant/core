"""Support for Pollen."""
from datetime import timedelta
import logging
import requests
from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Pollen Count'

ATTR_DATE_TAKEN = 'date_taken'

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pollen sensor platform."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error(
            "Latitude/Longitude has not been set in the Home Assistant config")
        return False

    add_entities([PollenSensor(PollenData(
        config.get(CONF_NAME),
        hass.config.latitude,
        hass.config.longitude
    ))], True)


class PollenSensor(Entity):
    """Representation of the Pollen sensor."""

    def __init__(self, pollen_data):
        """Initialize the Pollen sensor."""
        self._name = None
        self._state = None
        self._available = False
        self._date_taken = None
        self._pollen_data = pollen_data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DATE_TAKEN: self._date_taken
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:flower'

    def update(self):
        """Collect updated data from Pollen API."""
        self._pollen_data.update()

        self._name = self._pollen_data.name
        self._state = self._pollen_data.count
        self._available = self._pollen_data.avaliable
        self._date_taken = self._pollen_data.date_taken


class PollenData():
    """Pollen Data object."""

    def __init__(self, name, latitude, longitude):
        """Set up Pollen Sensor."""
        if name is not None:
            self.name = name
        else:
            self.name = DEFAULT_NAME
        self._url = "https://socialpollencount.co.uk{}[{},{}]".format(
            "/api/forecast?location=", latitude, longitude)
        self.count = None
        self.date_taken = None
        self.avaliable = None

    def update(self):
        """Update Pollen Sensor."""
        try:
            response = requests.get(self._url)
            response.raise_for_status()

            json = response.json()

            self.count = json["forecast"][0]["pollen_count"]
            self.date_taken = json["forecast"][0]["date"]

            self.avaliable = True

        except HTTPError as http_err:
            self.avaliable = False
            _LOGGER.error('A HTTP error occurred: %s', http_err)
