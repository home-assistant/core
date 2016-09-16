"""
Support for KNX thermostats.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.knx/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.components.knx import (KNXConfig, KNXMultiAddressDevice)
from homeassistant.const import (CONF_NAME, TEMP_CELSIUS, ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ADDRESS = 'address'
CONF_SETPOINT_ADDRESS = 'setpoint_address'
CONF_TEMPERATURE_ADDRESS = 'temperature_address'

DEFAULT_NAME = 'KNX Thermostat'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Required(CONF_SETPOINT_ADDRESS): cv.string,
    vol.Required(CONF_TEMPERATURE_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_devices([KNXThermostat(hass, KNXConfig(config))])


class KNXThermostat(KNXMultiAddressDevice, ClimateDevice):
    """Representation of a KNX thermostat.

    A KNX thermostat will has the following parameters:
    - temperature (current temperature)
    - setpoint (target temperature in HASS terms)
    - operation mode selection (comfort/night/frost protection)

    This version supports only polling. Messages from the KNX bus do not
    automatically update the state of the thermostat (to be implemented
    in future releases)
    """

    def __init__(self, hass, config):
        """Initialize the thermostat based on the given configuration."""
        KNXMultiAddressDevice.__init__(
            self, hass, config, ['temperature', 'setpoint'], ['mode'])

        self._unit_of_measurement = TEMP_CELSIUS  # KNX always used celsius
        self._away = False  # not yet supported
        self._is_fan_on = False  # not yet supported

    @property
    def should_poll(self):
        """Polling is needed for the KNX thermostat."""
        return True

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        from knxip.conversion import knx2_to_float

        return knx2_to_float(self.value('temperature'))

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        from knxip.conversion import knx2_to_float

        return knx2_to_float(self.value('setpoint'))

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        from knxip.conversion import float_to_knx2

        self.set_value('setpoint', float_to_knx2(temperature))
        _LOGGER.debug("Set target temperature to %s", temperature)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        raise NotImplementedError()
