"""Support for Radio Thermostat wifi-enabled home thermostats."""

from __future__ import annotations

import time
from typing import Any

import radiotherm

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_OFF,
    FAN_ON,
    PRESET_AWAY,
    PRESET_HOME,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN
from .coordinator import RadioThermUpdateCoordinator
from .entity import RadioThermostatEntity

ATTR_FAN_ACTION = "fan_action"

PRESET_HOLIDAY = "holiday"

PRESET_ALTERNATE = "alternate"

PRESET_DEFAULT = "default"

STATE_CIRCULATE = "circulate"

PRESET_MODES = [
    PRESET_DEFAULT,
    PRESET_HOME,
    PRESET_ALTERNATE,
    PRESET_AWAY,
    PRESET_HOLIDAY,
]

# HVAC operation list per model.
CT30_OPERATION_LIST = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
CT50_80_OPERATION_LIST = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.HEAT_COOL,
]
# Fan operation list per model.
CT30_50_FAN_OPERATION_LIST = [FAN_ON, FAN_AUTO]
CT80_FAN_OPERATION_LIST = [FAN_ON, STATE_CIRCULATE, FAN_AUTO]

# Mappings from radiotherm json data codes to and from Home Assistant state
# flags.  CODE is the thermostat integer code and these map to and
# from Home Assistant state flags.

# Programmed temperature mode of the thermostat.
CODE_TO_TEMP_MODE = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.HEAT_COOL,
}
TEMP_MODE_TO_CODE = {v: k for k, v in CODE_TO_TEMP_MODE.items()}

# Programmed fan mode (circulate is supported by CT80 models)
CODE_TO_FAN_MODE = {0: FAN_AUTO, 1: STATE_CIRCULATE, 2: FAN_ON}

FAN_MODE_TO_CODE = {v: k for k, v in CODE_TO_FAN_MODE.items()}

# Active thermostat state (is it heating or cooling?).  In the future
# this should probably made into heat and cool binary sensors.
CODE_TO_TEMP_STATE = {0: HVACAction.IDLE, 1: HVACAction.HEATING, 2: HVACAction.COOLING}

# Active fan state.  This is if the fan is actually on or not.  In the
# future this should probably made into a binary sensor for the fan.
CODE_TO_FAN_STATE = {0: FAN_OFF, 1: FAN_ON}

PRESET_MODE_TO_CODE = {
    PRESET_DEFAULT: -1,
    PRESET_HOME: 0,
    PRESET_ALTERNATE: 1,
    PRESET_AWAY: 2,
    PRESET_HOLIDAY: 3,
}

CODE_TO_PRESET_MODE = {v: k for k, v in PRESET_MODE_TO_CODE.items()}

PARALLEL_UPDATES = 1


def round_temp(temperature: float) -> float:
    """Round a temperature to the resolution of the thermostat.

    RadioThermostats can handle 0.5 degree temps so the input
    temperature is rounded to that value and returned.
    """
    return round(temperature * 2.0) / 2.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate for a radiotherm device."""
    coordinator: RadioThermUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RadioThermostat(coordinator)])


class RadioThermostat(RadioThermostatEntity, ClimateEntity):
    """Representation of a Radio Thermostat."""

    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_precision = PRECISION_HALVES
    _attr_name = None

    def __init__(self, coordinator: RadioThermUpdateCoordinator) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)

        # Common initialization.
        self._attr_unique_id = self.init_data.mac
        self._attr_target_temperature: float | None = None
        self._attr_target_temperature_high: float | None = None
        self._attr_target_temperature_low: float | None = None

        # Set common supported features.
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        # Add preset modes feature for CT80.
        if isinstance(self.device, radiotherm.thermostat.CT80):
            self._attr_preset_modes = PRESET_MODES
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        # Set hvac and fan modes depending on model.
        if isinstance(self.device, radiotherm.thermostat.CT30):
            self._attr_hvac_modes = CT30_OPERATION_LIST
            self._attr_fan_modes = CT30_50_FAN_OPERATION_LIST
        elif isinstance(self.device, radiotherm.thermostat.CT50):
            self._attr_hvac_modes = CT50_80_OPERATION_LIST
            self._attr_fan_modes = CT30_50_FAN_OPERATION_LIST
        else:
            self._attr_hvac_modes = CT50_80_OPERATION_LIST
            self._attr_fan_modes = CT80_FAN_OPERATION_LIST
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )

        # Process the already-available coordinator data so the ClimateEntity
        # has valid state from the very first render.
        self._process_data()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Turn fan on/off."""
        if (code := FAN_MODE_TO_CODE.get(fan_mode)) is None:
            raise ValueError(f"{fan_mode} is not a valid fan mode")
        await self.hass.async_add_executor_job(self._set_fan_mode, code)
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_fan_mode(self, code: int) -> None:
        """Turn fan on/off."""
        self.device.fmode = code

    @callback
    def _process_data(self) -> None:
        """Update and validate the data from the thermostat."""
        data = self.data.tstat

        # Map thermostat values into various STATE_ flags.
        self._attr_current_temperature = data["temp"]
        self._attr_fan_mode = CODE_TO_FAN_MODE[data["fmode"]]
        self._attr_extra_state_attributes = {
            ATTR_FAN_ACTION: CODE_TO_FAN_STATE[data["fstate"]]
        }
        self._attr_hvac_mode = CODE_TO_TEMP_MODE[data["tmode"]]

        # Determine current HVAC action.
        if self.hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = None
        elif data["tstate"] == 0 and data["fstate"] == 1:
            self._attr_hvac_action = HVACAction.FAN
        else:
            self._attr_hvac_action = CODE_TO_TEMP_STATE[data["tstate"]]

        # Set the targets, while failing gracefully.
        if self.hvac_mode == HVACMode.COOL:
            self._attr_target_temperature = data.get("t_cool")
        elif self.hvac_mode == HVACMode.HEAT:
            self._attr_target_temperature = data.get("t_heat")
        elif self.hvac_mode == HVACMode.HEAT_COOL:
            # If packet only contains one target, set only that target.
            if "t_heat" in data:
                self._attr_target_temperature_low = data["t_heat"]
            if "t_cool" in data:
                self._attr_target_temperature_high = data["t_cool"]

        # Set the CT80-only values
        if self.data.humidity is not None:
            self._attr_current_humidity = self.data.humidity
        if isinstance(self.device, radiotherm.thermostat.CT80):
            self._attr_preset_mode = CODE_TO_PRESET_MODE.get(data["program_mode"], 0)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temp_low is not None and temp_high is not None:
            await self.hass.async_add_executor_job(
                self._set_temperature_range, temp_low, temp_high
            )
            self._attr_target_temperature_low = round_temp(temp_low)
            self._attr_target_temperature_high = round_temp(temp_high)
        elif temperature is not None:
            await self.hass.async_add_executor_job(self._set_temperature, temperature)
            self._attr_target_temperature = round_temp(temperature)

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_temperature(self, temperature: float) -> None:
        """Set new target temperature."""
        temperature = round_temp(temperature)
        if self.hvac_mode == HVACMode.COOL:
            self.device.t_cool = temperature
        elif self.hvac_mode == HVACMode.HEAT:
            self.device.t_heat = temperature

    def _set_temperature_range(self, temp_low: float, temp_high: float) -> None:
        """Set heat/cool target temperature range."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            low_changed = round_temp(temp_low) != self._attr_target_temperature_low
            high_changed = round_temp(temp_high) != self._attr_target_temperature_high

            # Cannot consistently set both it_heat and it_cool in the same POST.
            # Therefore, update one or the other, or both with a delay between them.
            if low_changed:
                self.device.it_heat = round_temp(temp_low)
            if high_changed:
                if low_changed:
                    # if low also changed, then delay a second.
                    time.sleep(1)
                self.device.it_cool = round_temp(temp_high)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode (off, heat, cool, heat_cool)."""
        await self.hass.async_add_executor_job(self._set_hvac_mode, hvac_mode)
        self._attr_hvac_mode = hvac_mode

        # Immediately reconcile temperature attributes, where possible, for the new mode
        # so the card renders correctly before the next coordinator poll.
        data = self.data.tstat
        if hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = None
            self._attr_target_temperature = None
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None
        elif hvac_mode == HVACMode.COOL:
            self._attr_target_temperature = data.get("t_cool")
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None
        elif hvac_mode == HVACMode.HEAT:
            self._attr_target_temperature = data.get("t_heat")
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None
        elif hvac_mode == HVACMode.HEAT_COOL:
            self._attr_target_temperature = None
            self._attr_target_temperature_low = data.get("t_heat")
            self._attr_target_temperature_high = data.get("t_cool")

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode (off, heat, cool, heat_cool)."""

        if isinstance(self.device, radiotherm.thermostat.CT80):
            # Set the tmode directly.
            self.device.tmode = TEMP_MODE_TO_CODE[hvac_mode]
            return

        if hvac_mode in (HVACMode.OFF, HVACMode.HEAT_COOL):
            self.device.tmode = TEMP_MODE_TO_CODE[hvac_mode]
        # Setting t_cool or t_heat automatically changes tmode.
        elif hvac_mode == HVACMode.COOL:
            self.device.t_cool = self.target_temperature
        elif hvac_mode == HVACMode.HEAT:
            self.device.t_heat = self.target_temperature

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode (Home, Alternate, Away, Holiday)."""
        if preset_mode not in PRESET_MODES:
            raise ValueError(f"{preset_mode} is not a valid preset_mode")
        await self.hass.async_add_executor_job(self._set_preset_mode, preset_mode)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode (Home, Alternate, Away, Holiday)."""
        assert isinstance(self.device, radiotherm.thermostat.CT80)
        self.device.program_mode = PRESET_MODE_TO_CODE[preset_mode]
