"""
Support for eq3 Bluetooth Smart thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.eq3btsmart/
"""
import logging

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import TEMP_CELSIUS
from homeassistant.util.temperature import convert

REQUIREMENTS = ['bluepy_devices==0.2.0']

CONF_MAC = 'mac'
CONF_DEVICES = 'devices'
CONF_ID = 'id'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the eq3 BLE thermostats."""
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        mac = device_cfg[CONF_MAC]
        devices.append(EQ3BTSmartThermostat(mac, name))

    add_devices(devices)
    return True


# pylint: disable=too-many-instance-attributes, import-error, abstract-method
class EQ3BTSmartThermostat(ThermostatDevice):
    """Representation of a EQ3 Bluetooth Smart thermostat."""

    def __init__(self, _mac, _name):
        """Initialize the thermostat."""
        from bluepy_devices.devices import eq3btsmart

        self._name = _name

        self._thermostat = eq3btsmart.EQ3BTSmartThermostat(_mac)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Can not report temperature, so return target_temperature."""
        return self.target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._thermostat.target_temperature

    def set_temperature(self, temperature):
        """Set new target temperature."""
        self._thermostat.target_temperature = temperature

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {"mode": self._thermostat.mode,
                "mode_readable": self._thermostat.mode_readable}

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert(self._thermostat.min_temp, TEMP_CELSIUS,
                       self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert(self._thermostat.max_temp, TEMP_CELSIUS,
                       self.unit_of_measurement)

    def update(self):
        """Update the data from the thermostat."""
        self._thermostat.update()
