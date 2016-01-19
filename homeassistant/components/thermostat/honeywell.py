"""
homeassistant.components.thermostat.honeywell
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds support for Honeywell Round Connected and Honeywell Evohome thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.honeywell/
"""
import logging
import socket

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, TEMP_CELCIUS)

REQUIREMENTS = ['evohomeclient==0.2.4']

_LOGGER = logging.getLogger(__name__)

CONF_AWAY_TEMP = "away_temperature"


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the honeywel thermostat. """
    from evohomeclient import EvohomeClient

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    try:
        away_temp = float(config.get(CONF_AWAY_TEMP, 16))
    except ValueError:
        _LOGGER.error("value entered for item %s should convert to a number",
                      CONF_AWAY_TEMP)
        return False
    if username is None or password is None:
        _LOGGER.error("Missing required configuration items %s or %s",
                      CONF_USERNAME, CONF_PASSWORD)
        return False

    evo_api = EvohomeClient(username, password)

    try:
        zones = evo_api.temperatures(force_refresh=True)
        for i, zone in enumerate(zones):
            add_devices([RoundThermostat(evo_api,
                                         zone['id'],
                                         i == 0,
                                         away_temp)])
    except socket.error:
        _LOGGER.error(
            "Connection error logging into the honeywell evohome web service"
        )
        return False


class RoundThermostat(ThermostatDevice):
    """ Represents a Honeywell Round Connected thermostat. """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, device, zone_id, master, away_temp):
        self.device = device
        self._current_temperature = None
        self._target_temperature = None
        self._name = "round connected"
        self._id = zone_id
        self._master = master
        self._is_dhw = False
        self._away_temp = away_temp
        self._away = False
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
        if self._is_dhw:
            return None
        return self._target_temperature

    def set_temperature(self, temperature):
        """ Set new target temperature """
        self.device.set_temperature(self._name, temperature)

    @property
    def is_away_mode_on(self):
        """ Returns if away mode is on. """
        return self._away

    def turn_away_mode_on(self):
        """ Turns away on.
         Evohome does have a proprietary away mode, but it doesn't really work
         the way it should. For example: If you set a temperature manually
         it doesn't get overwritten when away mode is switched on.
         """
        self._away = True
        self.device.set_temperature(self._name, self._away_temp)

    def turn_away_mode_off(self):
        """ Turns away off. """
        self._away = False
        self.device.cancel_temp_override(self._name)

    def update(self):
        try:
            # Only refresh if this is the "master" device,
            # others will pick up the cache
            for val in self.device.temperatures(force_refresh=self._master):
                if val['id'] == self._id:
                    data = val

        except StopIteration:
            _LOGGER.error("Did not receive any temperature data from the "
                          "evohomeclient API.")
            return

        self._current_temperature = data['temp']
        self._target_temperature = data['setpoint']
        if data['thermostat'] == "DOMESTIC_HOT_WATER":
            self._name = "Hot Water"
            self._is_dhw = True
        else:
            self._name = data['name']
            self._is_dhw = False
