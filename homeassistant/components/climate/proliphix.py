"""
Support for Proliphix NT10e Thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.proliphix/
"""
import voluptuous as vol

from homeassistant.components.climate import (
    PRECISION_TENTHS, STATE_COOL, STATE_HEAT, STATE_IDLE,
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['proliphix==0.4.1']

ATTR_FAN = 'fan'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Proliphix thermostats."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)

    import proliphix

    pdp = proliphix.PDP(host, username, password)

    add_devices([ProliphixThermostat(pdp)])


class ProliphixThermostat(ClimateDevice):
    """Representation a Proliphix thermostat."""

    def __init__(self, pdp):
        """Initialize the thermostat."""
        self._pdp = pdp
        self._pdp.update()
        self._name = self._pdp.name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def should_poll(self):
        """Set up polling needed for thermostat."""
        return True

    def update(self):
        """Update the data from the thermostat."""
        self._pdp.update()

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def precision(self):
        """Return the precision of the system.

        Proliphix temperature values are passed back and forth in the
        API as tenths of degrees F (i.e. 690 for 69 degrees).
        """
        return PRECISION_TENTHS

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
        if state == 3:
            return STATE_HEAT
        if state == 6:
            return STATE_COOL

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._pdp.setback = temperature
