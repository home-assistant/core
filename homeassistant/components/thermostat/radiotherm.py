"""
homeassistant.components.thermostat.radiotherm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds support for Radio Thermostat wifi-enabled home thermostats
"""
import logging

from homeassistant.components.thermostat import (ThermostatDevice, STATE_COOL,
                                                 STATE_IDLE, STATE_HEAT)
from homeassistant.const import (CONF_HOST, CONF_NAME, TEMP_FAHRENHEIT)
from urllib.error import URLError

#TODO: investigate why this fails
# REQUIREMENTS = ['radiotherm-1.2']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Radio Thermostat. """
    logger = logging.getLogger(__name__)

    try:
        import radiotherm
    except ImportError:
        logger.exception(
            "Error while importing dependency radiotherm. "
            "Did you maybe not install the radiotherm dependency?")
        return

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    if host is None:
        logger.error("host not defined in config.")
        return

    try:
        tstat = radiotherm.get_thermostat(host)
    except URLError as err:
        logger.Exception(
            "Unable to connect to Radio Thermostat")
        return

    add_devices([RadioThermostat(tstat, name)])


class RadioThermostat(ThermostatDevice):
    """ Represent a Radio Thermostat. """

    def __init__(self, device, name=None):
        self.device = device
        if name:
            self.set_name(name)

    @property
    def name(self):
        """ Returns the name of the Radio Thermostat. """
        return self.device.name['raw']

    @property
    def unit_of_measurement(self):
        """ Unit of measurement this thermostat expresses itself in. """
        return TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        # Move these to Thermostat Device and make them global
        return {
            "humidity": None,
            "target_humidity": None,
            "fan": self.device.fmode['human'],
            "mode": self.device.tmode['human']
        }


    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return self.device.temp['raw']

    @property
    def operation(self):
        """ Returns current operation. head, cool idle """
        if self.device.tmode['human'] == 'Cool':
            return STATE_COOL
        elif self.device.tmode['human'] == 'Heat':
            return STATE_HEAT
        else:
            return STATE_IDLE

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """

        if self.operation == STATE_COOL:
            temp = self.device.t_cool['raw']
        elif self.operation == STATE_HEAT:
            temp = self.device.t_heat['raw']

        return round(temp, 1)


    def set_temperature(self, temperature):
        """ Set new target temperature """
        if self.operation == STATE_COOL:
            self.device.t_cool = temperature
        elif self.operation == STATE_HEAT:
            self.device.t_heat

    def set_name(self, name):
        """ Set thermostat name """
        self.device.name = name



