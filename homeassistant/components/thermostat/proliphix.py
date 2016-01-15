"""homeassistant.components.thermostat.proliphix
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Proliphix NT10e Thermostat is an ethernet connected thermostat. It
has a local HTTP interface that is based on get/set of OID values. A
complete collection of the API is available in this API doc:

https://github.com/sdague/thermostat.rb/blob/master/docs/PDP_API_R1_11.pdf
"""

from homeassistant.components.thermostat import (ThermostatDevice, STATE_COOL,
                                                 STATE_IDLE, STATE_HEAT)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 CONF_HOST, TEMP_FAHRENHEIT)

REQUIREMENTS = ['proliphix==0.1.0']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the proliphix thermostats. """
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
        return True

    def update(self):
        self._pdp.update()

    @property
    def name(self):
        """ Returns the name. """
        return self._name

    @property
    def device_state_attributes(self):
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
