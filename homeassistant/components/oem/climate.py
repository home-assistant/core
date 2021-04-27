"""OpenEnergyMonitor Thermostat Support."""
from oemthermostat import Thermostat
import requests
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default="Thermostat"): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
    }
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE
SUPPORT_HVAC = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the oemthermostat platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        therm = Thermostat(host, port=port, username=username, password=password)
    except (ValueError, AssertionError, requests.RequestException):
        return False

    add_entities((ThermostatDevice(therm, name),), True)


class ThermostatDevice(ClimateEntity):
    """Interface class for the oemthermostat module."""

    def __init__(self, thermostat, name):
        """Initialize the device."""
        self._name = name
        self.thermostat = thermostat

        # set up internal state varS
        self._state = None
        self._temperature = None
        self._setpoint = None
        self._mode = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._mode == 2:
            return HVAC_MODE_HEAT
        if self._mode == 1:
            return HVAC_MODE_AUTO
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC

    @property
    def name(self):
        """Return the name of this Thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_action(self):
        """Return current hvac i.e. heat, cool, idle."""
        if not self._mode:
            return CURRENT_HVAC_OFF
        if self._state:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._setpoint

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            self.thermostat.mode = 1
        elif hvac_mode == HVAC_MODE_HEAT:
            self.thermostat.mode = 2
        elif hvac_mode == HVAC_MODE_OFF:
            self.thermostat.mode = 0

    def set_temperature(self, **kwargs):
        """Set the temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        self.thermostat.setpoint = temp

    def update(self):
        """Update local state."""
        self._setpoint = self.thermostat.setpoint
        self._temperature = self.thermostat.temperature
        self._state = self.thermostat.state
        self._mode = self.thermostat.mode
