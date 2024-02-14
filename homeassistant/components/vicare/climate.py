"""Viessmann ViCare climate device."""
from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import HeatingCircuit as PyViCareHeatingCircuit
from PyViCare.PyViCareUtils import (
    PyViCareCommandError,
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests
import voluptuous as vol

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VICARE_API, VICARE_DEVICE_CONFIG
from .entity import ViCareEntity
from .utils import get_burners, get_circuits, get_compressors

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_VICARE_MODE = "set_vicare_mode"
SERVICE_SET_VICARE_MODE_ATTR_MODE = "vicare_mode"

VICARE_MODE_DHW = "dhw"
VICARE_MODE_HEATING = "heating"
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

VICARE_TO_HA_HVAC_HEATING: dict[str, HVACMode] = {
    VICARE_MODE_FORCEDREDUCED: HVACMode.OFF,
    VICARE_MODE_OFF: HVACMode.OFF,
    VICARE_MODE_DHW: HVACMode.OFF,
    VICARE_MODE_DHWANDHEATINGCOOLING: HVACMode.AUTO,
    VICARE_MODE_DHWANDHEATING: HVACMode.AUTO,
    VICARE_MODE_HEATING: HVACMode.AUTO,
    VICARE_MODE_FORCEDNORMAL: HVACMode.HEAT,
}

VICARE_TO_HA_PRESET_HEATING = {
    VICARE_PROGRAM_COMFORT: PRESET_COMFORT,
    VICARE_PROGRAM_ECO: PRESET_ECO,
    VICARE_PROGRAM_NORMAL: PRESET_HOME,
    VICARE_PROGRAM_REDUCED: PRESET_SLEEP,
}

HA_TO_VICARE_PRESET_HEATING = {
    PRESET_COMFORT: VICARE_PROGRAM_COMFORT,
    PRESET_ECO: VICARE_PROGRAM_ECO,
    PRESET_HOME: VICARE_PROGRAM_NORMAL,
    PRESET_SLEEP: VICARE_PROGRAM_REDUCED,
}


def _build_entities(
    api: PyViCareDevice,
    device_config: PyViCareDeviceConfig,
) -> list[ViCareClimate]:
    """Create ViCare climate entities for a device."""
    return [
        ViCareClimate(
            api,
            circuit,
            device_config,
            "heating",
        )
        for circuit in get_circuits(api)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ViCare climate platform."""
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]
    device_config = hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG]

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_VICARE_MODE,
        {vol.Required(SERVICE_SET_VICARE_MODE_ATTR_MODE): cv.string},
        "set_vicare_mode",
    )

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            api,
            device_config,
        )
    )


class ViCareClimate(ViCareEntity, ClimateEntity):
    """Representation of the ViCare heating climate device."""

    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = VICARE_TEMP_HEATING_MIN
    _attr_max_temp = VICARE_TEMP_HEATING_MAX
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_preset_modes = list(HA_TO_VICARE_PRESET_HEATING)
    _current_action: bool | None = None
    _current_mode: str | None = None
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        api: PyViCareDevice,
        circuit: PyViCareHeatingCircuit,
        device_config: PyViCareDeviceConfig,
        translation_key: str,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(device_config, api, circuit.id)
        self._circuit = circuit
        self._attributes: dict[str, Any] = {}
        self._current_program = None
        self._attr_translation_key = translation_key

    def update(self) -> None:
        """Let HA know there has been an update from the ViCare API."""
        try:
            _room_temperature = None
            with suppress(PyViCareNotSupportedFeatureError):
                _room_temperature = self._circuit.getRoomTemperature()

            _supply_temperature = None
            with suppress(PyViCareNotSupportedFeatureError):
                _supply_temperature = self._circuit.getSupplyTemperature()

            if _room_temperature is not None:
                self._attr_current_temperature = _room_temperature
            elif _supply_temperature is not None:
                self._attr_current_temperature = _supply_temperature
            else:
                self._attr_current_temperature = None

            with suppress(PyViCareNotSupportedFeatureError):
                self._current_program = self._circuit.getActiveProgram()

            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_target_temperature = (
                    self._circuit.getCurrentDesiredTemperature()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                self._current_mode = self._circuit.getActiveMode()

            # Update the generic device attributes
            self._attributes = {
                "room_temperature": _room_temperature,
                "active_vicare_program": self._current_program,
                "active_vicare_mode": self._current_mode,
            }

            with suppress(PyViCareNotSupportedFeatureError):
                self._attributes[
                    "heating_curve_slope"
                ] = self._circuit.getHeatingCurveSlope()

            with suppress(PyViCareNotSupportedFeatureError):
                self._attributes[
                    "heating_curve_shift"
                ] = self._circuit.getHeatingCurveShift()

            self._attributes["vicare_modes"] = self._circuit.getModes()

            self._current_action = False
            # Update the specific device attributes
            with suppress(PyViCareNotSupportedFeatureError):
                for burner in get_burners(self._api):
                    self._current_action = self._current_action or burner.getActive()

            with suppress(PyViCareNotSupportedFeatureError):
                for compressor in get_compressors(self._api):
                    self._current_action = (
                        self._current_action or compressor.getActive()
                    )

        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current hvac mode."""
        if self._current_mode is None:
            return None
        return VICARE_TO_HA_HVAC_HEATING.get(self._current_mode, None)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new hvac mode on the ViCare API."""
        if "vicare_modes" not in self._attributes:
            raise ValueError("Cannot set hvac mode when vicare_modes are not known")

        vicare_mode = self.vicare_mode_from_hvac_mode(hvac_mode)
        if vicare_mode is None:
            raise ValueError(f"Cannot set invalid hvac mode: {hvac_mode}")

        _LOGGER.debug("Setting hvac mode to %s / %s", hvac_mode, vicare_mode)
        self._circuit.setMode(vicare_mode)

    def vicare_mode_from_hvac_mode(self, hvac_mode):
        """Return the corresponding vicare mode for an hvac_mode."""
        if "vicare_modes" not in self._attributes:
            return None

        supported_modes = self._attributes["vicare_modes"]
        for key, value in VICARE_TO_HA_HVAC_HEATING.items():
            if key in supported_modes and value == hvac_mode:
                return key
        return None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac modes."""
        if "vicare_modes" not in self._attributes:
            return []

        supported_modes = self._attributes["vicare_modes"]
        hvac_modes = []
        for key, value in VICARE_TO_HA_HVAC_HEATING.items():
            if value in hvac_modes:
                continue
            if key in supported_modes:
                hvac_modes.append(value)
        return hvac_modes

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current hvac action."""
        if self._current_action:
            return HVACAction.HEATING
        return HVACAction.IDLE

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._circuit.setProgramTemperature(self._current_program, temp)
            self._attr_target_temperature = temp

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return VICARE_TO_HA_PRESET_HEATING.get(self._current_program)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode and deactivate any existing programs."""
        target_program = HA_TO_VICARE_PRESET_HEATING.get(preset_mode)
        if target_program is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="program_unknown",
                translation_placeholders={
                    "preset": preset_mode,
                },
            )

        _LOGGER.debug("Current preset %s", self._current_program)
        if self._current_program and self._current_program not in [
            VICARE_PROGRAM_NORMAL,
            VICARE_PROGRAM_REDUCED,
            VICARE_PROGRAM_STANDBY,
        ]:
            # We can't deactivate "normal", "reduced" or "standby"
            _LOGGER.debug("deactivating %s", self._current_program)
            try:
                self._circuit.deactivateProgram(self._current_program)
            except PyViCareCommandError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="program_not_deactivated",
                    translation_placeholders={
                        "program": self._current_program,
                    },
                ) from err

        _LOGGER.debug("Setting preset to %s / %s", preset_mode, target_program)
        if target_program not in [
            VICARE_PROGRAM_NORMAL,
            VICARE_PROGRAM_REDUCED,
            VICARE_PROGRAM_STANDBY,
        ]:
            # And we can't explicitly activate "normal", "reduced" or "standby", either
            _LOGGER.debug("activating %s", target_program)
            try:
                self._circuit.activateProgram(target_program)
            except PyViCareCommandError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="program_not_activated",
                    translation_placeholders={
                        "program": target_program,
                    },
                ) from err

    @property
    def extra_state_attributes(self):
        """Show Device Attributes."""
        return self._attributes

    def set_vicare_mode(self, vicare_mode):
        """Service function to set vicare modes directly."""
        if vicare_mode not in self._attributes["vicare_modes"]:
            raise ValueError(f"Cannot set invalid vicare mode: {vicare_mode}.")

        self._circuit.setMode(vicare_mode)
