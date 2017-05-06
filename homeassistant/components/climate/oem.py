"""
OpenEnergyMonitor Thermostat Support.

This provides a climate component for the ESP8266 based thermostat sold by
OpenEnergyMonitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.oem/
"""
import logging

import requests
import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, STATE_HEAT, STATE_IDLE, ATTR_TEMPERATURE)
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PORT, TEMP_CELSIUS, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['oemthermostat==1.1']

_LOGGER = logging.getLogger(__name__)

CONF_AWAY_TEMP = 'away_temp'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default="Thermostat"): cv.string,
    vol.Optional(CONF_PORT, default=80): cv.port,
    vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
    vol.Optional(CONF_AWAY_TEMP, default=14): vol.Coerce(float)
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the oemthermostat platform."""
    from oemthermostat import Thermostat

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    away_temp = config.get(CONF_AWAY_TEMP)

    try:
        therm = Thermostat(
            host, port=port, username=username, password=password)
    except (ValueError, AssertionError, requests.RequestException):
        return False

    add_devices((ThermostatDevice(hass, therm, name, away_temp), ), True)


class ThermostatDevice(ClimateDevice):
    """Interface class for the oemthermostat modul."""

    def __init__(self, hass, thermostat, name, away_temp):
        """Initialize the device."""
        self._name = name
        self.hass = hass

        # Away mode stuff
        self._away = False
        self._away_temp = away_temp
        self._prev_temp = thermostat.setpoint

        self.thermostat = thermostat
        # Set the thermostat mode to manual
        self.thermostat.mode = 2

        # set up internal state varS
        self._state = None
        self._temperature = None
        self._setpoint = None

    @property
    def name(self):
        """Return the name of this Thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation i.e. heat, cool, idle."""
        if self._state:
            return STATE_HEAT
        else:
            return STATE_IDLE

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._setpoint

    def set_temperature(self, **kwargs):
        """Set the temperature."""
        # If we are setting the temp, then we don't want away mode anymore.
        self.turn_away_mode_off()

        temp = kwargs.get(ATTR_TEMPERATURE)
        self.thermostat.setpoint = temp

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    def turn_away_mode_on(self):
        """Turn away mode on."""
        if not self._away:
            self._prev_temp = self._setpoint

        self.thermostat.setpoint = self._away_temp
        self._away = True

    def turn_away_mode_off(self):
        """Turn away mode off."""
        if self._away:
            self.thermostat.setpoint = self._prev_temp

        self._away = False

    def update(self):
        """Update local state."""
        self._setpoint = self.thermostat.setpoint
        self._temperature = self.thermostat.temperature
        self._state = self.thermostat.state
