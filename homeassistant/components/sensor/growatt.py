"""
Support for Growatt Plant energy production sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.growatt/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_USERNAME,
                                 CONF_PASSWORD)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['growatt_api_client==0.0.1']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

UNIT = 'kWh'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Growatt Plant sensor"""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    sensor_today = GrowattPlantToday(hass, username, password)
    sensor_total = GrowattPlantTotal(hass, username, password)

    add_entities([sensor_today, sensor_total])


class GrowattPlant(Entity):
    """Representation of a Growatt plant sensor."""

    def __init__(self, hass, username, password):
        """Initialize the sensor."""
        self._hass = hass
        self._unit_of_measurement = UNIT
        self._state = None

        from growatt_api.growatt_api import GrowattApi
        self._username = username
        self._password = password
        self.client = GrowattApi()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class GrowattPlantToday(GrowattPlant):
    """Representation of a Growatt plant daily sensor."""

    def update(self):
        """Get the latest data from Growatt server."""
        self._state = self.client.todays_energy_total(self._username, self._password)

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Growatt plant today'


class GrowattPlantTotal(GrowattPlant):
    """Representation of a Growatt plant total sensor."""

    def update(self):
        """Get the latest data from Growatt server."""
        self._state = self.client.global_energy_total(self._username, self._password)

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Growatt plant total'
