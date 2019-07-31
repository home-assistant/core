""" Plugwise Climate component for HomeAssistant.  """

import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (PLATFORM_SCHEMA, ClimateDevice)
from homeassistant.components.climate.const import (CURRENT_HVAC_HEAT,
                                                    CURRENT_HVAC_IDLE,
                                                    HVAC_MODE_AUTO,
                                                    HVAC_MODE_OFF,
                                                    SUPPORT_PRESET_MODE,
                                                    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (ATTR_TEMPERATURE, CONF_HOST, CONF_NAME,
                                 CONF_PASSWORD, CONF_PORT, CONF_USERNAME,
                                 TEMP_CELSIUS)
from homeassistant.exceptions import PlatformNotReady

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)

_LOGGER = logging.getLogger(__name__)

# Configuration directives
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'

# Default directives
DEFAULT_NAME = 'Plugwise Thermostat'
DEFAULT_USERNAME = 'smile'
DEFAULT_TIMEOUT = 10
DEFAULT_PORT = 80
DEFAULT_ICON = 'mdi:thermometer'
DEFAULT_MIN_TEMP = 4
DEFAULT_MAX_TEMP = 30

# HVAC modes
ATTR_HVAC_MODES = [HVAC_MODE_AUTO, HVAC_MODE_OFF]

# Read platform configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): cv.positive_int,
    vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add the Plugwise (Anna) Thermostate."""
    add_devices([
        ThermostatDevice(
            config.get(CONF_NAME),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            config.get(CONF_HOST),
            config.get(CONF_PORT),
            config.get(CONF_MIN_TEMP),
            config.get(CONF_MAX_TEMP),
        )
    ])


class ThermostatDevice(ClimateDevice):
    """Representation of an Plugwise thermostat."""

    def __init__(self, name, username, password, host, port,
                 min_temp, max_temp):
        """Set up the Plugwise API."""
        _LOGGER.debug("Init called")
        self._name = name
        self._username = username
        self._password = password
        self._host = host
        self._port = port
        self._temperature = None
        self._current_temperature = None
        self._outdoor_temperature = None
        self._state = None
        self._active_schema = None
        self._previous_schema = None
        self._preset_mode = None
        self._preset_modes = []
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._hvac_modes = ATTR_HVAC_MODES
        self._hvac_mode = None
        self._available_schemas = []

        _LOGGER.debug("Initializing API")
        import haanna
        self._api = haanna.Haanna(self._username, self._password,
                                  self._host, self._port)
        try:
            self._api.ping_anna_thermostat()
        except Exception:
            _LOGGER.error("Unable to ping, platform not ready")
            raise PlatformNotReady
        _LOGGER.debug("Platform ready")
        self.update()

    @property
    def should_poll(self):
        """Return that we will require polling."""
        return True

    @property
    def hvac_action(self):
        """Return the current action."""
        if self._api.get_heating_status(self._domain_objects) is True:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return DEFAULT_ICON

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = {}
        attributes['outdoor_temperature'] = self._outdoor_temperature
        attributes['available_schemas'] = self._api.get_schema_names(
            self._domain_objects)
        attributes['active_schema'] = self._active_schema
        attributes['previous_schema'] = self._previous_schema
        return attributes

    def update(self):
        """Update the data from the thermostat."""
        _LOGGER.debug("Update called")
        self._domain_objects = self._api.get_domain_objects()
        self._outdoor_temperature = self._api.get_outdoor_temperature(
            self._domain_objects)
        api_active_schema = self._api.get_active_schema_name(
            self._domain_objects)
        if self._active_schema != api_active_schema:
            self._previous_schema = self._active_schema
            self._active_schema = api_active_schema

    @property
    def hvac_mode(self):
        """Return current active hvac state."""
        if self._api.get_schema_state(self._domain_objects) is True:
            return HVAC_MODE_AUTO
        return HVAC_MODE_OFF

    @property
    def preset_mode(self):
        """Return the active preset mode."""
        return self._api.get_current_preset(self._domain_objects)

    @property
    def preset_modes(self):
        """Return the available preset modes list without values."""
        presets = list(self._api.get_presets(self._domain_objects).keys())
        return presets

    @property
    def hvac_modes(self):
        """Return the available hvac  modes list."""
        return self._hvac_modes

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._api.get_temperature(self._domain_objects)

    @property
    def min_temp(self):
        """Return the minimal temperature possible to set."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature possible to set."""
        return self._max_temp

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._api.get_target_temperature(self._domain_objects)

    @property
    def temperature_unit(self):
        """Return the unit of measured temperature."""
        return TEMP_CELSIUS

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.debug("Adjusting temperature")
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if (temperature is not None and self._min_temp < temperature
                < self._max_temp):
            self._temperature = temperature
            self._api.set_temperature(self._domain_objects, temperature)
            _LOGGER.debug("Changing temporary temperature")
        else:
            _LOGGER.error("Invalid temperature requested")

    def set_hvac_mode(self, hvac_mode):
        """Set the hvac mode."""
        _LOGGER.debug("Adjusting hvac_mode (i.e. schedule/schema)")
        if self._previous_schema is None and self._active_schema is None:
            _LOGGER.error("previous_schema not known, unable to apply")
        else:
            if self._previous_schema is None:
                schema = self._active_schema
            else:
                schema = self._previous_schema
            schema_mode = 'false'
            if hvac_mode == HVAC_MODE_AUTO:
                schema_mode = 'true'
            self._api.set_schema_state(self._domain_objects, schema,
                                       schema_mode)

    def set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        _LOGGER.debug("Adjusting preset_mode (i.e. preset)")
        if preset_mode in self._preset_modes:
            self._preset_mode = preset_mode
            self._api.set_preset(self._domain_objects, preset_mode)
            _LOGGER.debug("Changing preset mode")
        else:
            _LOGGER.error("Invalid or no preset mode given")
