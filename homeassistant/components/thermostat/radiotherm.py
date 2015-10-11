"""
homeassistant.components.thermostat.radiotherm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds support for Radio Thermostat wifi-enabled home thermostats
"""
import logging
import datetime
from urllib.error import URLError

from homeassistant.components.thermostat import (ThermostatDevice, STATE_COOL,
                                                 STATE_IDLE, STATE_HEAT)
from homeassistant.const import (CONF_HOST, TEMP_FAHRENHEIT)

REQUIREMENTS = ['radiotherm==1.2']


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

    # Detect hosts with hass discovery, config or radiotherm discovery
    hosts = []
    if discovery_info:
        logger.info('hass radiotherm discovery: %s', discovery_info)
    elif CONF_HOST in config:
        hosts = [config[CONF_HOST]]
    else:
        hosts.append(radiotherm.discover.discover_address())

    if hosts is None:
        logger.error("no radiotherm thermostats detected")
        return

    tstats = []

    for host in hosts:
        try:
            tstat = radiotherm.get_thermostat(host)
            tstats.append(RadioThermostat(tstat))
        except (URLError, OSError):
            logger.exception(
                "Unable to connect to Radio Thermostat: %s", host)

    add_devices(tstats)


class RadioThermostat(ThermostatDevice):
    """ Represent a Radio Thermostat. """

    def __init__(self, device, name=None):
        self.device = device
        if name:
            self.set_name(name)
        self.set_time()
        self._away = False
        self._away_cool = 82
        self._away_heat = 70

    @property
    def name(self):
        """ Returns the name of the Radio Thermostat. """
        return self.device.name['raw']

    def set_name(self, name):
        """ Set thermostat name """
        self.device.name = name

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
            self.device.t_heat = temperature

    @property
    def is_away_mode_on(self):
        """ Returns away mode """
        return self._away

    def turn_away_mode_on(self):
        """ Turns away mode on. """
        self._away = True

    def turn_away_mode_off(self):
        """ Turns away mode off. """
        self._away = False

    def set_time(self):
        """ Set device time """
        now = datetime.datetime.now()
        self.device.time = {'day': now.weekday(),
                            'hour': now.hour, 'minute': now.minute}
