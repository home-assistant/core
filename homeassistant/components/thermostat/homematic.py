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
    if discovery_info:
        return homematic.setup_hmdevice_discovery_helper(HMThermostat,
                                                         discovery_info,
                                                         add_callback_devices)
    # Manual
    return homematic.setup_hmdevice_entity_helper(HMThermostat,
                                                  config,
                                                  add_callback_devices)


# pylint: disable=abstract-method
class HMThermostat(homematic.HMDevice, ThermostatDevice):
    """Represents a Homematic Thermostat in Home Assistant."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if not self.available:
            return None
        return self._data["ACTUAL_TEMPERATURE"]

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if not self.available:
            return None
        return self._data["SET_TEMPERATURE"]

    def set_temperature(self, temperature):
        """Set new target temperature."""
        if not self.available:
            return None
        self._hmdevice.set_temperature(temperature)

    @property
    def min_temp(self):
        """Return the minimum temperature - 4.5 means off."""
        return convert(4.5, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature - 30.5 means on."""
        return convert(30.5, TEMP_CELSIUS, self.unit_of_measurement)

    def _check_hm_to_ha_object(self):
        """Check if possible to use the HM Object as this HA type."""
        from pyhomematic.devicetypes.thermostats import HMThermostat\
            as pyHMThermostat

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # Check if the homematic device correct for this HA device
        if isinstance(self._hmdevice, pyHMThermostat):
            return True

        _LOGGER.critical("This %s can't be use as thermostat", self._name)
        return False

    def _init_data_struct(self):
        """Generate a data dict (self._data) from hm metadata."""
        super()._init_data_struct()

        # Add state to data dict
        self._data.update({"CONTROL_MODE": STATE_UNKNOWN,
                           "SET_TEMPERATURE": STATE_UNKNOWN,
                           "ACTUAL_TEMPERATURE": STATE_UNKNOWN})
