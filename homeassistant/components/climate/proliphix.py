"""
Support for Proliphix NT10e Thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.proliphix/
"""
import voluptuous as vol

from homeassistant.components.climate import (
    STATE_COOL, STATE_HEAT, STATE_IDLE, ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['proliphix==0.4.0']

ATTR_FAN = 'fan'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Proliphix thermostats."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)
    max_temp = config.get(CONF_MAX_TEMP)
    min_temp = config.get(CONF_MIN_TEMP)

    import proliphix

    pdp = proliphix.PDP(host, username, password)

    add_devices([ProliphixThermostat(pdp, min_temp, max_temp)])


class ProliphixThermostat(ClimateDevice):
    """Representation a Proliphix thermostat."""

    def __init__(self, pdp, min_temp=None, max_temp=None):
        """Initialize the thermostat."""
        self._pdp = pdp
        # initial data
        self._pdp.update()
        self._name = self._pdp.name
        self._min_temp = min_temp
        self._max_temp = max_temp

    @property
    def should_poll(self):
        """Polling needed for thermostat."""
        return True

    def update(self):
        """Update the data from the thermostat."""
        self._pdp.update()

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_FAN: self._pdp.fan_state
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._pdp.cur_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._pdp.setback

    @property
    def current_operation(self):
        """Return the current state of the thermostat."""
        state = self._pdp.hvac_state
        if state in (1, 2):
            return STATE_IDLE
        elif state == 3:
            return STATE_HEAT
        elif state == 6:
            return STATE_COOL

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        # pylint: disable=no-member
        if self._min_temp:
            return self._min_temp
        else:
            # get default temp from super class
            return ClimateDevice.min_temp.fget(self)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        # pylint: disable=no-member
        if self._max_temp:
            return self._max_temp
        else:
            # Get default temp from super class
            return ClimateDevice.max_temp.fget(self)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._pdp.setback = temperature
