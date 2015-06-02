"""
Adds support for Nest thermostats.
"""
import logging

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, TEMP_CELCIUS)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the nest thermostat. """
    logger = logging.getLogger(__name__)

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if username is None or password is None:
        logger.error("Missing required configuration items %s or %s",
                     CONF_USERNAME, CONF_PASSWORD)
        return

    try:
        import nest
    except ImportError:
        logger.exception(
            "Error while importing dependency nest. "
            "Did you maybe not install the python-nest dependency?")

        return

    napi = nest.Nest(username, password)

    add_devices([
        NestThermostat(structure, device)
        for structure in napi.structures
        for device in structure.devices
    ])


class NestThermostat(ThermostatDevice):
    """ Represents a Nest thermostat within Home Assistant. """

    def __init__(self, structure, device):
        self.structure = structure
        self.device = device

    @property
    def name(self):
        """ Returns the name of the nest, if any. """
        return self.device.name

    @property
    def unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return TEMP_CELCIUS

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        # Move these to Thermostat Device and make them global
        return {
            "humidity": self.device.humidity,
            "target_humidity": self.device.target_humidity,
            "fan": self.device.fan,
            "mode": self.device.mode
        }

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return round(self.device.temperature, 1)

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        return round(self.device.target, 1)

    @property
    def is_away_mode_on(self):
        """ Returns if away mode is on. """
        return self.structure.away

    def set_temperature(self, temperature):
        """ Set new target temperature """
        self.device.target = temperature

    def turn_away_mode_on(self):
        """ Turns away on. """
        self.structure.away = True

    def turn_away_mode_off(self):
        """ Turns away off. """
        self.structure.away = False

    def update(self):
        """ Python-nest has its own mechanism for staying up to date. """
        pass
