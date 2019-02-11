"""
Support for Growatt Plant energy production sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.growatt/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_USERNAME,
                                 CONF_PASSWORD)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['growatt==0.0.2']

_LOGGER = logging.getLogger(__name__)

UNIT = 'kWh'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Growatt Plant sensor."""
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

        import growatt
        self._username = username
        self._password = password
        self.client = growatt.GrowattApi()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @staticmethod
    def _extract_energy(plant_info_data, key):
        """Extract energy as float from a string."""
        kwhs = [_[key] for _ in plant_info_data]
        energies = [float(_.split(' ')[0]) for _ in kwhs]
        return sum(energies)

    def _plant_info(self, username: str, password: str):
        import growatt
        try:
            self.client.login(username, password)
        except growatt.LoginError as error:
            logging.error(error)
        return self.client.plant_list()

    def todays_energy_total(self):
        """Get todays energy as float in kWh."""
        plant_info = self._plant_info(self._username, self._password)
        return self._extract_energy(plant_info['data'], 'todayEnergy')

    def global_energy_total(self):
        """Get total historic energy as float in kWh."""
        plant_info = self._plant_info(self._username, self._password)
        return self._extract_energy(plant_info['data'], 'totalEnergy')


class GrowattPlantToday(GrowattPlant):
    """Representation of a Growatt plant daily sensor."""

    def update(self):
        """Get the latest data from Growatt server."""
        self._state = self.todays_energy_total()

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Growatt plant today'


class GrowattPlantTotal(GrowattPlant):
    """Representation of a Growatt plant total sensor."""

    def update(self):
        """Get the latest data from Growatt server."""
        self._state = self.global_energy_total()

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Growatt plant total'
