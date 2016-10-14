"""
Support for eQ-3 Bluetooth Smart thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.eq3btsmart/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MAC, TEMP_CELSIUS, CONF_DEVICES, ATTR_TEMPERATURE)
from homeassistant.util.temperature import convert
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['bluepy_devices==0.2.0']

_LOGGER = logging.getLogger(__name__)

ATTR_MODE = 'mode'
ATTR_MODE_READABLE = 'mode_readable'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES):
        vol.Schema({cv.string: DEVICE_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the eQ-3 BLE thermostats."""
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        mac = device_cfg[CONF_MAC]
        devices.append(EQ3BTSmartThermostat(mac, name))

    add_devices(devices)


# pylint: disable=too-many-instance-attributes, import-error, abstract-method
class EQ3BTSmartThermostat(ClimateDevice):
    """Representation of a eQ-3 Bluetooth Smart thermostat."""

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
    def temperature_unit(self):
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

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._thermostat.target_temperature = temperature

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_MODE: self._thermostat.mode,
            ATTR_MODE_READABLE: self._thermostat.mode_readable,
        }

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
