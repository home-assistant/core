"""
homeassistant.components.thermostat.proliphix
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The Proliphix NT10e Thermostat is an ethernet connected thermostat.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.proliphix/
"""
from homeassistant.components.thermostat import (
    STATE_COOL, STATE_HEAT, STATE_IDLE, ThermostatDevice)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, TEMP_FAHRENHEIT)

REQUIREMENTS = ['proliphix==0.1.0']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Proliphix thermostats. """
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)

    import proliphix

    pdp = proliphix.PDP(host, username, password)

    add_devices([
        ProliphixThermostat(pdp)
    ])


class ProliphixThermostat(ThermostatDevice):
    """ Represents a Proliphix thermostat. """

    def __init__(self, pdp):
        self._pdp = pdp
        # initial data
        self._pdp.update()
        self._name = self._pdp.name

    @property
    def should_poll(self):
        """ Polling needed for thermostat.. """
        return True

    def update(self):
        """ Update the data from the thermostat. """
        self._pdp.update()

    @property
    def name(self):
        """ Returns the name of the thermostat. """
        return self._name

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        return {
            "fan": self._pdp.fan_state
        }

    @property
    def unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return self._pdp.cur_temp

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        return self._pdp.setback_heat

    @property
    def operation(self):
        """ Returns the current state of the thermostat. """
        state = self._pdp.hvac_state
        if state in (1, 2):
            return STATE_IDLE
        elif state == 3:
            return STATE_HEAT
        elif state == 6:
            return STATE_COOL

    def set_temperature(self, temperature):
        """ Set new target temperature. """
        self._pdp.setback_heat = temperature
