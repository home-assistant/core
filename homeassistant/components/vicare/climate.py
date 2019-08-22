"""
Viessmann ViCare climate device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/vicare/
"""

import logging
import voluptuous as vol

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    PRESET_ECO,
    PRESET_COMFORT,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
)
from homeassistant.const import (
    TEMP_CELSIUS,
    ATTR_TEMPERATURE,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
    PRECISION_WHOLE,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ["PyViCare==0.0.30"]

CONF_CIRCUIT = "circuit"

VICARE_MODE_DHW = "dhw"
VICARE_MODE_DHWANDHEATING = "dhwAndHeating"
VICARE_MODE_FORCEDREDUCED = "forcedReduced"
VICARE_MODE_FORCEDNORMAL = "forcedNormal"
VICARE_MODE_OFF = "standby"

VICARE_PROGRAM_ACTIVE = "active"
VICARE_PROGRAM_COMFORT = "comfort"
VICARE_PROGRAM_ECO = "eco"
VICARE_PROGRAM_EXTERNAL = "external"
VICARE_PROGRAM_HOLIDAY = "holiday"
VICARE_PROGRAM_NORMAL = "normal"
VICARE_PROGRAM_REDUCED = "reduced"
VICARE_PROGRAM_STANDBY = "standby"

VICARE_HOLD_MODE_AWAY = "away"
VICARE_HOLD_MODE_HOME = "home"
VICARE_HOLD_MODE_OFF = "off"

VICARE_TEMP_WATER_MIN = 10
VICARE_TEMP_WATER_MAX = 60
VICARE_TEMP_HEATING_MIN = 3
VICARE_TEMP_HEATING_MAX = 37

SUPPORT_FLAGS_HEATING = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_FLAGS_WATER = SUPPORT_TARGET_TEMPERATURE

VICARE_TO_HA_HVAC_HEATING = {
    VICARE_MODE_DHW: HVAC_MODE_OFF,
    VICARE_MODE_DHWANDHEATING: HVAC_MODE_AUTO,
    VICARE_MODE_FORCEDREDUCED: HVAC_MODE_OFF,
    VICARE_MODE_FORCEDNORMAL: HVAC_MODE_HEAT,
    VICARE_MODE_OFF: HVAC_MODE_OFF,
}

HA_TO_VICARE_HVAC_HEATING = {
    HVAC_MODE_HEAT: VICARE_MODE_FORCEDNORMAL,
    HVAC_MODE_OFF: VICARE_MODE_FORCEDREDUCED,
    HVAC_MODE_AUTO: VICARE_MODE_DHWANDHEATING,
}

VICARE_TO_HA_HVAC_DHW = {
    VICARE_MODE_DHW: HVAC_MODE_AUTO,
    VICARE_MODE_DHWANDHEATING: HVAC_MODE_AUTO,
    VICARE_MODE_FORCEDREDUCED: HVAC_MODE_OFF,
    VICARE_MODE_FORCEDNORMAL: HVAC_MODE_AUTO,
    VICARE_MODE_OFF: HVAC_MODE_OFF,
}

HA_TO_VICARE_HVAC_DHW = {
    HVAC_MODE_OFF: VICARE_MODE_OFF,
    HVAC_MODE_AUTO: VICARE_MODE_DHW,
}

VALUE_UNKNOWN = "unknown"

PYVICARE_ERROR = "error"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CIRCUIT, default=-1): int,
        vol.Optional(CONF_NAME, default="ViCare"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the ViCare climate devices."""
    from PyViCare import ViCareSession

    if config.get(CONF_CIRCUIT) == -1:
        vicare_api = ViCareSession(
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            "/tmp/vicare_token.save",
        )
    else:
        vicare_api = ViCareSession(
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            "/tmp/vicare_token.save",
            config.get(CONF_CIRCUIT),
        )
    add_entities(
        [
            ViCareClimate(hass, config.get(CONF_NAME) + " Heating", vicare_api),
            ViCareWater(hass, config.get(CONF_NAME) + " Water", vicare_api),
        ]
    )


class ViCareClimate(ClimateDevice):
    """Representation of the ViCare heating climate device."""

    def __init__(self, hass, name, api):
        """Initialize the climate device."""
        self._name = name
        self._state = None
        self._api = api
        self._support_flags = SUPPORT_FLAGS_HEATING
        self._unit_of_measurement = hass.config.units.temperature_unit
        self._target_temperature = None
        self._current_mode = VALUE_UNKNOWN
        self._current_temperature = None
        self._current_program = VALUE_UNKNOWN

    def update(self):
        """Let HA know there has been an update from the ViCare API."""
        _room_temperature = self._api.getRoomTemperature()
        if _room_temperature is not None and _room_temperature != "error":
            self._current_temperature = _room_temperature
        else:
            self._current_temperature = self._api.getBoilerTemperature()
        self._current_program = self._api.getActiveProgram()

        # The getCurrentDesiredTemperature call can yield 'error' (str) when the system is in standby
        desired_temperature = self._api.getCurrentDesiredTemperature()
        if desired_temperature == PYVICARE_ERROR:
            desired_temperature = None

        self._target_temperature = desired_temperature

        self._current_mode = self._api.getActiveMode()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current hvac mode."""
        return VICARE_TO_HA_HVAC_HEATING.get(self._current_mode, STATE_UNKNOWN)

    def set_hvac_mode(self, hvac_mode):
        """Set a new hvac mode on the ViCare API."""
        _LOGGER.info(
            "setting hvac mode to %s (%s)",
            hvac_mode,
            HA_TO_VICARE_HVAC_HEATING.get(hvac_mode, STATE_UNKNOWN),
        )
        self._api.setMode(HA_TO_VICARE_HVAC_HEATING.get(hvac_mode, STATE_UNKNOWN))
        self.async_schedule_update_ha_state(True)

    @property
    def hvac_modes(self):
        """Return the list of available hvac modes."""
        return list(HA_TO_VICARE_HVAC_HEATING.keys())

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(
            VICARE_TEMP_HEATING_MIN, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(
            VICARE_TEMP_HEATING_MAX, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self._api.setProgramTemperature(self._current_program, self._target_temperature)
        self.schedule_update_ha_state()

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._current_program == VICARE_PROGRAM_COMFORT:
            return PRESET_COMFORT
        if self._current_program == VICARE_PROGRAM_ECO:
            return PRESET_ECO
        return None

    @property
    def preset_modes(self):
        """Return the available preset mode."""
        return [PRESET_COMFORT, PRESET_ECO]

    def set_preset_mode(self, preset_mode):
        """Set new preset mode and deactivate any existing programs."""
        self._api.deactivateProgram(self._current_program)

        if preset_mode == PRESET_COMFORT:
            self._api.activateProgram(VICARE_PROGRAM_COMFORT)
        elif preset_mode == PRESET_ECO:
            self._api.activateProgram(VICARE_PROGRAM_ECO)


class ViCareWater(ClimateDevice):
    """Representation of the ViCare domestic hot water device."""

    def __init__(self, hass, name, api):
        """Initialize the DHW climate device."""
        self._name = name
        self._state = None
        self._api = api
        self._support_flags = SUPPORT_FLAGS_WATER
        self._unit_of_measurement = hass.config.units.temperature_unit
        self._target_temperature = None
        self._current_temperature = None
        self._current_mode = VALUE_UNKNOWN

    def update(self):
        """Let HA know there has been an update from the ViCare API."""
        current_temperature = self._api.getDomesticHotWaterStorageTemperature()
        if current_temperature is not None and current_temperature != "error":
            self._current_temperature = current_temperature
        else:
            self._current_temperature = -1

        self._target_temperature = self._api.getDomesticHotWaterConfiguredTemperature()

        self._current_mode = self._api.getActiveMode()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        else:
            return

        self._api.setDomesticHotWaterTemperature(self._target_temperature)

        self.schedule_update_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(
            VICARE_TEMP_WATER_MIN, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(
            VICARE_TEMP_WATER_MAX, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def hvac_mode(self):
        """Return current hvac mode."""
        return VICARE_TO_HA_HVAC_DHW.get(self._current_mode, STATE_UNKNOWN)

    def set_hvac_mode(self, hvac_mode):
        """Set a new hvac mode on the ViCare API."""
        _LOGGER.error(
            "The DHW climate device does not support setting modes."
            "The current mode is only informative since. Setting it might conflict with the heating climate device"
        )

    @property
    def hvac_modes(self):
        """Return the list of available hvac modes."""
        return list(HA_TO_VICARE_HVAC_DHW.keys())

    @property
    def preset_modes(self):
        """Return the available preset mode."""
        return []
