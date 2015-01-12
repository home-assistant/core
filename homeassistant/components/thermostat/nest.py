"""
Adds support for Nest thermostats.
"""
import logging

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, TEMP_CELCIUS, TEMP_FAHRENHEIT)


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Gets Nest thermostats. """
    logger = logging.getLogger(__name__)

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if username is None or password is None:
        logger.error("Missing required configuration items %s or %s",
                     CONF_USERNAME, CONF_PASSWORD)
        return []

    try:
        # pylint: disable=no-name-in-module, unused-variable
        import homeassistant.external.pynest.nest as pynest  # noqa
    except ImportError:
        logger.exception("Error while importing dependency phue.")

        return []

    return [NestThermostat(username, password)]


class NestThermostat(ThermostatDevice):
    """ Represents a Nest thermostat within Home Assistant. """

    def __init__(self, username, password):
        # pylint: disable=no-name-in-module, import-error
        import homeassistant.external.pynest.nest as pynest

        self.nest = pynest.Nest(username, password)
        self.nest.login()
        self.update()

    @property
    def name(self):
        """ Returns the name of the nest, if any. """
        return "Nest"  # TODO Possible to get actual name from Nest device?

    @property
    def unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return TEMP_FAHRENHEIT if self.nest.units == 'F' else TEMP_CELCIUS

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        return None

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return self.nest.get_curtemp()

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        return self.nest.get_tartemp()

    @property
    def is_away_mode_on(self):
        """ Returns if away mode is on. """
        return self.nest.is_away()

    def set_temperature(self, temperature):
        """ Set new target temperature """
        self.nest.set_temperature(temperature)

    def turn_away_mode_on(self):
        """ Turns away on. """
        self.nest.set_away("away")

    def turn_away_mode_off(self):
        """ Turns away off. """
        self.nest.set_away("here")

    def update(self):
        """ Update nest. """
        self.nest.get_status()
