"""Viessmann ViCare climate device."""
import logging

import requests

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_COMFORT,
    PRESET_ECO,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS

from . import (
    DOMAIN as VICARE_DOMAIN,
    VICARE_API,
    VICARE_HEATING_TYPE,
    VICARE_NAME,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)

VICARE_MODE_DHW = "dhw"
VICARE_MODE_DHWANDHEATING = "dhwAndHeating"
VICARE_MODE_DHWANDHEATINGCOOLING = "dhwAndHeatingCooling"
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

VICARE_TEMP_HEATING_MIN = 3
VICARE_TEMP_HEATING_MAX = 37

SUPPORT_FLAGS_HEATING = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

VICARE_TO_HA_HVAC_HEATING = {
    VICARE_MODE_DHW: HVAC_MODE_OFF,
    VICARE_MODE_DHWANDHEATING: HVAC_MODE_AUTO,
    VICARE_MODE_DHWANDHEATINGCOOLING: HVAC_MODE_AUTO,
    VICARE_MODE_FORCEDREDUCED: HVAC_MODE_OFF,
    VICARE_MODE_FORCEDNORMAL: HVAC_MODE_HEAT,
    VICARE_MODE_OFF: HVAC_MODE_OFF,
}

HA_TO_VICARE_HVAC_HEATING = {
    HVAC_MODE_HEAT: VICARE_MODE_FORCEDNORMAL,
    HVAC_MODE_OFF: VICARE_MODE_FORCEDREDUCED,
    HVAC_MODE_AUTO: VICARE_MODE_DHWANDHEATING,
}

VICARE_TO_HA_PRESET_HEATING = {
    VICARE_PROGRAM_COMFORT: PRESET_COMFORT,
    VICARE_PROGRAM_ECO: PRESET_ECO,
}

HA_TO_VICARE_PRESET_HEATING = {
    PRESET_COMFORT: VICARE_PROGRAM_COMFORT,
    PRESET_ECO: VICARE_PROGRAM_ECO,
}

PYVICARE_ERROR = "error"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the ViCare climate devices."""
    if discovery_info is None:
        return
    vicare_api = hass.data[VICARE_DOMAIN][VICARE_API]
    heating_type = hass.data[VICARE_DOMAIN][VICARE_HEATING_TYPE]
    add_entities(
        [
            ViCareClimate(
                f"{hass.data[VICARE_DOMAIN][VICARE_NAME]}  Heating",
                vicare_api,
                heating_type,
            )
        ]
    )


class ViCareClimate(ClimateDevice):
    """Representation of the ViCare heating climate device."""

    def __init__(self, name, api, heating_type):
        """Initialize the climate device."""
        self._name = name
        self._state = None
        self._api = api
        self._attributes = {}
        self._target_temperature = None
        self._current_mode = None
        self._current_temperature = None
        self._current_program = None
        self._heating_type = heating_type
        self._current_action = None

    def update(self):
        """Let HA know there has been an update from the ViCare API."""
        try:
            _room_temperature = self._api.getRoomTemperature()
            _supply_temperature = self._api.getSupplyTemperature()
            if _room_temperature is not None and _room_temperature != PYVICARE_ERROR:
                self._current_temperature = _room_temperature
            elif _supply_temperature != PYVICARE_ERROR:
                self._current_temperature = _supply_temperature
            else:
                self._current_temperature = None
            self._current_program = self._api.getActiveProgram()

            # The getCurrentDesiredTemperature call can yield 'error' (str) when the system is in standby
            desired_temperature = self._api.getCurrentDesiredTemperature()
            if desired_temperature == PYVICARE_ERROR:
                desired_temperature = None

            self._target_temperature = desired_temperature

            self._current_mode = self._api.getActiveMode()

            # Update the generic device attributes
            self._attributes = {}
            self._attributes["room_temperature"] = _room_temperature
            self._attributes["supply_temperature"] = _supply_temperature
            self._attributes["outside_temperature"] = self._api.getOutsideTemperature()
            self._attributes["active_vicare_program"] = self._current_program
            self._attributes["active_vicare_mode"] = self._current_mode
            self._attributes["heating_curve_slope"] = self._api.getHeatingCurveSlope()
            self._attributes["heating_curve_shift"] = self._api.getHeatingCurveShift()
            self._attributes[
                "month_since_last_service"
            ] = self._api.getMonthSinceLastService()
            self._attributes["date_last_service"] = self._api.getLastServiceDate()
            self._attributes["error_history"] = self._api.getErrorHistory()
            self._attributes["active_error"] = self._api.getActiveError()
            self._attributes[
                "circulationpump_active"
            ] = self._api.getCirculationPumpActive()

            # Update the specific device attributes
            if self._heating_type == HeatingType.gas:
                self._current_action = self._api.getBurnerActive()

                self._attributes["burner_modulation"] = self._api.getBurnerModulation()
                self._attributes[
                    "boiler_temperature"
                ] = self._api.getBoilerTemperature()

            elif self._heating_type == HeatingType.heatpump:
                self._current_action = self._api.getCompressorActive()

                self._attributes[
                    "return_temperature"
                ] = self._api.getReturnTemperature()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATING

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

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
        return VICARE_TO_HA_HVAC_HEATING.get(self._current_mode)

    def set_hvac_mode(self, hvac_mode):
        """Set a new hvac mode on the ViCare API."""
        vicare_mode = HA_TO_VICARE_HVAC_HEATING.get(hvac_mode)
        if vicare_mode is None:
            _LOGGER.error(
                "Cannot set invalid vicare mode: %s / %s", hvac_mode, vicare_mode
            )
            return

        _LOGGER.debug("Setting hvac mode to %s / %s", hvac_mode, vicare_mode)
        self._api.setMode(vicare_mode)

    @property
    def hvac_modes(self):
        """Return the list of available hvac modes."""
        return list(HA_TO_VICARE_HVAC_HEATING)

    @property
    def hvac_action(self):
        """Return the current hvac action."""
        if self._current_action:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return VICARE_TEMP_HEATING_MIN

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return VICARE_TEMP_HEATING_MAX

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            self._api.setProgramTemperature(self._current_program, temp)
            self._target_temperature = temp

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return VICARE_TO_HA_PRESET_HEATING.get(self._current_program)

    @property
    def preset_modes(self):
        """Return the available preset mode."""
        return list(VICARE_TO_HA_PRESET_HEATING)

    def set_preset_mode(self, preset_mode):
        """Set new preset mode and deactivate any existing programs."""
        vicare_program = HA_TO_VICARE_PRESET_HEATING.get(preset_mode)
        if vicare_program is None:
            _LOGGER.error(
                "Cannot set invalid vicare program: %s / %s",
                preset_mode,
                vicare_program,
            )
            return

        _LOGGER.debug("Setting preset to %s / %s", preset_mode, vicare_program)
        self._api.deactivateProgram(self._current_program)
        self._api.activateProgram(vicare_program)

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self._attributes
