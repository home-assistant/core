"""
homeassistant.components.thermostat.honeywell_round_connected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds support for Honeywell Round Connected thermostats.
"""
import socket
import logging
from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, TEMP_CELCIUS)

REQUIREMENTS = ['evohomeclient==0.2.3']


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
        from evohomeclient import EvohomeClient
    except ImportError:
        logger.exception(
            "Error while importing dependency evohomeclient. "
            "Did you maybe not install the python evohomeclient dependency?")

        return

    evo_api = EvohomeClient(username, password)
    try:
        add_devices([
            RoundThermostat(evo_api)
        ])
    except socket.error:
        logger.error(
            "Connection error logging into the honeywell evohome web service"
        )


class RoundThermostat(ThermostatDevice):
    """ Represents a Honeywell Round Connected thermostat. """

    def __init__(self, device):
        self.device = device
        self._current_temperature = None
        self._target_temperature = None
        self._name = "round connected"
        self._sensorid = None
        self.update()

    @property
    def name(self):
        """ Returns the name of the nest, if any. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit of measurement this thermostat expresses itself in. """
        return TEMP_CELCIUS

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        # Move these to Thermostat Device and make them global
        return {}

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return self._current_temperature

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        return self._target_temperature

    def set_temperature(self, temperature):
        """ Set new target temperature """
        self.device.set_temperature(self._name, temperature)

    @property
    def should_poll(self):
        """ Should poll the evohome cloud service """
        return True

    def update(self):
        for dev in self.device.temperatures(force_refresh=True):
            self._current_temperature = dev['temp']
            self._target_temperature = dev['setpoint']
            self._name = dev['name']
            self._sensorid = dev['id']
