__author__ = 'sander'

"""
homeassistant.components.thermostat.honeywell_round_connected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds support for Honeywell Round Connected thermostats.
"""
import socket
import logging

from homeassistant.components.thermostat import (ThermostatDevice, STATE_COOL,
                                                 STATE_IDLE, STATE_HEAT)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, TEMP_CELCIUS)

REQUIREMENTS = ['evohomeclient==0.2.3']

# from . import ATTR_CURRENT_TEMPERATURE,ATTR_TEMPERATURE

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
        #self.structure = structure
        self.device = device
        self._current_temperature=None
        self._target_temperature=None
        self._name="round connected"
        self._sensorid=None
        self.update()


    @property
    def name(self):
        """ Returns the name of the nest, if any. """
        return self._name

    @name.setter
    def name(self,value):
        self._name=value

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


    # @property
    # def operation(self):
    #     """ Returns current operation ie. heat, cool, idle """
    #     if self.device.hvac_ac_state is True:
    #         return STATE_COOL
    #     elif self.device.hvac_heater_state is True:
    #         return STATE_HEAT
    #     else:
    #         return STATE_IDLE

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        return self._target_temperature



    # @property
    # def target_temperature_low(self):
    #     """ Returns the lower bound temperature we try to reach. """
    #     if self.device.mode == 'range':
    #         return round(self.device.target[0], 1)
    #     return round(self.target_temperature, 1)
    #
    # @property
    # def target_temperature_high(self):
    #     """ Returns the upper bound temperature we try to reach. """
    #     if self.device.mode == 'range':
    #         return round(self.device.target[1], 1)
    #     return round(self.target_temperature, 1)
    #
    # @property
    # def is_away_mode_on(self):
    #     """ Returns if away mode is on. """
    #     return True

    def set_temperature(self, temperature):
        """ Set new target temperature """
        self.device.set_temperature(self._name,temperature)


    def turn_away_mode_on(self):
        """ Turns away on. """
        self.structure.away = True

    def turn_away_mode_off(self):
        """ Turns away off. """
        self.structure.away = False

    # @property
    # def min_temp(self):
    #     """ Identifies min_temp in Nest API or defaults if not available. """
    #     temp = self.device.away_temperature.low
    #     if temp is None:
    #         return super().min_temp
    #     else:
    #         return temp

    # @property
    # def max_temp(self):
    #     """ Identifies mxn_temp in Nest API or defaults if not available. """
    #     temp = self.device.away_temperature.high
    #     if temp is None:
    #         return super().max_temp
    #     else:
    #         return temp

    @property
    def should_poll(self):
        """ Should poll the evohome cloud service """
        return True

    def update(self):
        for dev in self.device.temperatures(force_refresh=True):
            self._current_temperature=dev['temp']
            self._target_temperature=dev['setpoint']
            self._name=dev['name']
            self._sensorid=dev['id']

