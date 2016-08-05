"""
Support for Homematic thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.homematic/
"""
import logging
import homeassistant.components.homematic as homematic
from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.util.temperature import convert
from homeassistant.const import TEMP_CELSIUS, STATE_UNKNOWN

DEPENDENCIES = ['homematic']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the Homematic thermostat platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(HMThermostat,
                                                     discovery_info,
                                                     add_callback_devices)


# pylint: disable=abstract-method
class HMThermostat(homematic.HMDevice, ThermostatDevice):
    """Representation of a Homematic thermostat."""

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
        """Check if possible to use the Homematic object as this HA type."""
        from pyhomematic.devicetypes.thermostats import HMThermostat\
            as pyHMThermostat

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # Check if the Homematic device correct for this HA device
        if isinstance(self._hmdevice, pyHMThermostat):
            return True

        _LOGGER.critical("This %s can't be use as thermostat", self._name)
        return False

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        super()._init_data_struct()

        # Add state to data dict
        self._data.update({"CONTROL_MODE": STATE_UNKNOWN,
                           "SET_TEMPERATURE": STATE_UNKNOWN,
                           "ACTUAL_TEMPERATURE": STATE_UNKNOWN})
