"""
homeassistant.components.thermostat.honeywell
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds support for Honeywell Round Connected thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.honeywell/
"""
import socket
import logging
from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, TEMP_CELCIUS)

REQUIREMENTS = ['evohomeclient==0.2.3']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the honeywel thermostat. """
    from evohomeclient import EvohomeClient

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if username is None or password is None:
        _LOGGER.error("Missing required configuration items %s or %s",
                      CONF_USERNAME, CONF_PASSWORD)
        return False

    evo_api = EvohomeClient(username, password)
    try:
        add_devices([RoundThermostat(evo_api)])
    except socket.error:
        _LOGGER.error(
            "Connection error logging into the honeywell evohome web service"
        )
        return False


class RoundThermostat(ThermostatDevice):
    """ Represents a Honeywell Round Connected thermostat. """

    def __init__(self, device):
        self.device = device
        self._current_temperature = None
        self._target_temperature = None
        self._name = "round connected"
        self.update()

    @property
    def name(self):
        """ Returns the name of the honeywell, if any. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit of measurement this thermostat expresses itself in. """
        return TEMP_CELCIUS

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

    def update(self):
        try:
            # Only take first thermostat data from API for now
            data = next(self.device.temperatures(force_refresh=True))
        except StopIteration:
            _LOGGER.error("Did not receive any temperature data from the "
                          "evohomeclient API.")
            return

        self._current_temperature = data['temp']
        self._target_temperature = data['setpoint']
        self._name = data['name']
