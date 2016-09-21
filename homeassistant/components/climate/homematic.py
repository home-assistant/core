"""
Support for Homematic thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.homematic/
"""
import logging
import homeassistant.components.homematic as homematic
from homeassistant.components.climate import ClimateDevice, STATE_AUTO
from homeassistant.util.temperature import convert
from homeassistant.const import TEMP_CELSIUS, STATE_UNKNOWN, ATTR_TEMPERATURE

DEPENDENCIES = ['homematic']

STATE_MANUAL = "manual"
STATE_BOOST = "boost"

HM_STATE_MAP = {
    "AUTO_MODE": STATE_AUTO,
    "MANU_MODE": STATE_MANUAL,
    "BOOST_MODE": STATE_BOOST,
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the Homematic thermostat platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(
        HMThermostat,
        discovery_info,
        add_callback_devices
    )


# pylint: disable=abstract-method
class HMThermostat(homematic.HMDevice, ClimateDevice):
    """Representation of a Homematic thermostat."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if not self.available:
            return None

        # read state and search
        for mode, state in HM_STATE_MAP.items():
            code = getattr(self._hmdevice, mode, 0)
            if self._data.get('CONTROL_MODE') == code:
                return state

    @property
    def operation_list(self):
        """List of available operation modes."""
        if not self.available:
            return None
        op_list = []

        # generate list
        for mode in self._hmdevice.ACTIONNODE:
            if mode in HM_STATE_MAP:
                op_list.append(HM_STATE_MAP.get(mode))

        return op_list

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if not self.available:
            return None
        return self._data.get('ACTUAL_HUMIDITY', None)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if not self.available:
            return None
        return self._data.get('ACTUAL_TEMPERATURE', None)

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if not self.available:
            return None
        return self._data.get('SET_TEMPERATURE', None)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if not self.available:
            return None
        if temperature is None:
            return

        if self.current_operation == STATE_AUTO:
            return self._hmdevice.actionNodeData('MANU_MODE', temperature)
        self._hmdevice.set_temperature(temperature)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        for mode, state in HM_STATE_MAP.items():
            if state == operation_mode:
                code = getattr(self._hmdevice, mode, 0)
                self._hmdevice.MODE = code

    @property
    def min_temp(self):
        """Return the minimum temperature - 4.5 means off."""
        return convert(4.5, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature - 30.5 means on."""
        return convert(30.5, TEMP_CELSIUS, self.unit_of_measurement)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        # Add state to data dict
        self._data.update({"CONTROL_MODE": STATE_UNKNOWN,
                           "SET_TEMPERATURE": STATE_UNKNOWN,
                           "ACTUAL_TEMPERATURE": STATE_UNKNOWN})

        # support humidity
        if 'ACTUAL_HUMIDITY' in self._hmdevice.SENSORNODE:
            self._data.update({'ACTUAL_HUMIDITY': STATE_UNKNOWN})
