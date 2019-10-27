"""Plugwise Climate component for HomeAssistant."""

import logging

import voluptuous as vol
import haanna

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_AUTO,
    SUPPORT_PRESET_MODE,
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
from homeassistant.exceptions import PlatformNotReady

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

_LOGGER = logging.getLogger(__name__)

# Configuration directives
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_LEGACY = "legacy_anna"

# Default directives
DEFAULT_NAME = "Plugwise Thermostat"
DEFAULT_USERNAME = "smile"
DEFAULT_TIMEOUT = 10
DEFAULT_PORT = 80
DEFAULT_ICON = "mdi:thermometer"
DEFAULT_MIN_TEMP = 4
DEFAULT_MAX_TEMP = 30

# New CURRENT_HVAC mode
CURRENT_HVAC_DHW = "dhw"

# HVAC modes
ATTR_HVAC_MODES_1 = [HVAC_MODE_HEAT, HVAC_MODE_AUTO]
ATTR_HVAC_MODES_2 = [HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO]

# Read platform configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_LEGACY, default=False): cv.boolean,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): cv.positive_int,
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Add the Plugwise (Anna) Thermostate."""
    api = haanna.Haanna(
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[CONF_HOST],
        config[CONF_PORT],
        config[CONF_LEGACY],
    )
    try:
        api.ping_anna_thermostat()
    except OSError:
        _LOGGER.debug("Ping failed, retrying later", exc_info=True)
        raise PlatformNotReady
    devices = [
        ThermostatDevice(
            api, config[CONF_NAME], config[CONF_MIN_TEMP], config[CONF_MAX_TEMP]
        )
    ]
    async_add_entities(devices)


class ThermostatDevice(ClimateDevice):
    """Representation of an Plugwise thermostat."""

    def __init__(self, api, name, min_temp, max_temp):
        """Set up the Plugwise API."""
        self._api = api
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._name = name
        self._domain_objects = None
        self._outdoor_temperature = None
        self._selected_schema = None
        self._preset_mode = None
        self._presets = None
        self._presets_list = None
        self._heating_status = None
        self._cooling_status = None
        self._dhw_status = None
        self._schema_names = None
        self._schema_status = None
        self._current_temperature = None
        self._thermostat_temperature = None
        self._illuminance = None
        self._boiler_temperature = None
        self._water_pressure = None
        self._schedule_temperature = None
        self._hvac_mode = None
        self._hvac_modes_1 = ATTR_HVAC_MODES_1
        self._hvac_modes_2 = ATTR_HVAC_MODES_2

    @property
    def hvac_action(self):
        """Return the current action."""
        if self._heating_status:
            return CURRENT_HVAC_HEAT
        if self._cooling_status:
            return CURRENT_HVAC_COOL
        if self._dhw_status:
            return CURRENT_HVAC_DHW
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
        if self._outdoor_temperature is not None:
            attributes["outdoor_temperature"] = self._outdoor_temperature
        attributes["available_schemas"] = self._schema_names
        attributes["selected_schema"] = self._selected_schema
        if self._illuminance is not None:
            attributes["illuminance"] = self._illuminance
        if self._boiler_temperature is not None:
            attributes["boiler_temperature"] = self._boiler_temperature
        if self._water_pressure is not None:
            attributes["water_pressure"] = self._water_pressure
        return attributes

    @property
    def preset_modes(self):
        """Return the available preset modes list and make the presets with their temperatures available."""
        return self._presets_list

    @property
    def hvac_modes(self):
        """Return the available hvac modes list."""
        if self._heating_status is not None:
            if self._cooling_status is not None:
                return self._hvac_modes_2
            return self._hvac_modes_1

    @property
    def hvac_mode(self):
        """Return current active hvac state."""
        if self._schema_status:
            return HVAC_MODE_AUTO
        if self._heating_status is not None:
            if self._cooling_status is not None:
                return HVAC_MODE_HEAT_COOL
            return HVAC_MODE_HEAT

    @property
    def thermostat_temperature(self):
        """Return the thermostat set_temperature.

        This setting directly follows the changes in temperature from the interface or schedule. After a small delay, the target_temperature value will change as well, this is some kind of filter-function.
        """
        return self._thermostat_temperature

    @property
    def target_temperature(self):
        """Return the target_temperature.

        From the XML the thermostat-value is used because it updates 'immediately' compared to the target_temperature-value. This way the information on the card is "immediately" updated after changing the preset, temperature, etc.
        """
        return self._thermostat_temperature

    @property
    def preset_mode(self):
        """Return the active selected schedule-name, or the (temporary) active preset or Temporary in case of a manual change in the set-temperature."""
        if self._presets is not None:
            presets = self._presets
            preset_temperature = presets.get(self._preset_mode, "none")
            if self.hvac_mode == HVAC_MODE_AUTO:
                if self._thermostat_temperature == self._schedule_temperature:
                    return "{}".format(self._selected_schema)
                if self._thermostat_temperature == preset_temperature:
                    return self._preset_mode
                return "Temporary"
            if self._thermostat_temperature != preset_temperature:
                return "Manual"
            return self._preset_mode

    @property
    def current_temperature(self):
        """Return the current room temperature."""
        return self._current_temperature

    @property
    def min_temp(self):
        """Return the minimal temperature possible to set."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature possible to set."""
        return self._max_temp

    @property
    def temperature_unit(self):
        """Return the unit of measured temperature."""
        return TEMP_CELSIUS

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.debug("Adjusting temperature")
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None and self._min_temp < temperature < self._max_temp:
            _LOGGER.debug("Changing temporary temperature")
            self._api.set_temperature(self._domain_objects, temperature)
        else:
            _LOGGER.error("Invalid temperature requested")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the hvac mode."""
        _LOGGER.debug("Adjusting hvac_mode (i.e. schedule/schema)")
        schema_mode = "false"
        if hvac_mode == HVAC_MODE_AUTO:
            schema_mode = "true"
        self._api.set_schema_state(
            self._domain_objects, self._selected_schema, schema_mode
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        _LOGGER.debug("Changing preset mode")
        self._api.set_preset(self._domain_objects, preset_mode)

    async def async_update(self):
        """Update the data from the thermostat."""
        _LOGGER.debug("Update called")
        self._domain_objects = self._api.get_domain_objects()
        self._outdoor_temperature = self._api.get_outdoor_temperature(
            self._domain_objects
        )
        self._selected_schema = self._api.get_active_schema_name(self._domain_objects)
        self._preset_mode = self._api.get_current_preset(self._domain_objects)
        self._presets = self._api.get_presets(self._domain_objects)
        self._presets_list = list(self._api.get_presets(self._domain_objects))
        self._heating_status = self._api.get_heating_status(self._domain_objects)
        self._cooling_status = self._api.get_cooling_status(self._domain_objects)
        self._dhw_status = self._api.get_domestic_hot_water_status(self._domain_objects)
        self._schema_names = self._api.get_schema_names(self._domain_objects)
        self._schema_status = self._api.get_schema_state(self._domain_objects)
        self._current_temperature = self._api.get_current_temperature(
            self._domain_objects
        )
        self._thermostat_temperature = self._api.get_thermostat_temperature(
            self._domain_objects
        )
        self._schedule_temperature = self._api.get_schedule_temperature(
            self._domain_objects
        )
        self._illuminance = self._api.get_illuminance(self._domain_objects)
        self._boiler_temperature = self._api.get_boiler_temperature(
            self._domain_objects
        )
        self._water_pressure = self._api.get_water_pressure(self._domain_objects)
