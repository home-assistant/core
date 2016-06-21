"""
The Homematic thermostat platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration:

thermostat:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    name: "<User defined name>" (optional)
"""

import logging
import homeassistant.components.homematic as homematic
from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.helpers.temperature import convert
from homeassistant.const import TEMP_CELSIUS, STATE_UNKNOWN

DEPENDENCIES = ['homematic']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    return homematic.setup_hmdevice_entity_helper(HMThermostat,
                                                  config,
                                                  add_callback_devices)


class HMThermostat(homematic.HMDevice, ThermostatDevice):
    """Represents an Homematic Thermostat in Home Assistant."""

    def __init__(self, config):
        """Initialize generic HM device."""
        super().__init__(config)

        self.__current_temperature = None
        self.__set_temperature = None
        self.__mode = None
        self.__away_mode = None
        self.__auto_mode = None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if not self.available:
            return None
        return self._data[self.__current_temperature]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if not self.available:
            return None
        return self._data[self.__set_temperature]

    def set_temperature(self, temperature):
        """Set new target temperature."""
        if not self.available:
            return None

        self._hmdevice.set_temperature(temperature)
        self._data[self.__set_temperature] = temperature

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        if not self.available:
            return None

        return self._data[self.__mode] == self.__away_mode

    def turn_away_mode_on(self):
        """Turn away mode on."""
        if not self.available:
            return None
        self._hmdevice.PARTYMODE = True
        self._data[self.__mode] = self.__away_mode

    def turn_away_mode_off(self):
        """Turn away mode off."""
        if not self.available:
            return None
        self._hmdevice.AUTOMODE = False
        self._data[self.__mode] = self.__auto_mode

    @property
    def min_temp(self):
        """Return the minimum temperature - 4.5 means off."""
        return convert(4.5, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature - 30.5 means on."""
        return convert(30.5, TEMP_CELSIUS, self.unit_of_measurement)

    def _check_hm_to_ha_object(self):
        """
        Check if possible to use the HM Object as this HA type
        NEED overwrite by inheret!
        """
        import pyhomematic.devicetypes.thermostats

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # check if the homematic device correct for this HA device
        if isinstance(self._hmdevice, devicetypes.thermostats.HMThermostat):
            return True

        _LOGGER.critical("This %s can't be use as thermostat", self._name)
        return False

    def _init_data_struct(self):
        """
        Generate a data struct (self._data) from hm metadata
        NEED overwrite by inheret!
        """
        self.__current_temperature = "ACTUAL_TEMPERATURE"
        self.__set_temperature = "SET_TEMPERATURE"
        self.__mode = "CONTROL_MODE"
        self.__auto_mode = self._hmdevice.AUTO_MODE
        self.__away_mode = self._hmdevice.PARTY_MODE

        # add state to data struct
        self._data.update({self.__mode: STATE_UNKNOWN,
                           self.__set_temperature: STATE_UNKNOWN,
                           self.__current_temperature: STATE_UNKNOWN})
