"""Support for Z-Wave climate devices."""
from enum import IntEnum
import logging
from typing import Optional, Tuple

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_NONE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

VALUE_LIST = "List"
VALUE_ID = "Value"
VALUE_LABEL = "Label"
VALUE_SELECTED_ID = "Selected_id"
VALUE_SELECTED_LABEL = "Selected"

ATTR_FAN_ACTION = "fan_action"
ATTR_VALVE_POSITION = "valve_position"
_LOGGER = logging.getLogger(__name__)


class ThermostatMode(IntEnum):
    """Enum with all (known/used) Z-Wave ThermostatModes."""

    # https://github.com/OpenZWave/open-zwave/blob/master/cpp/src/command_classes/ThermostatMode.cpp
    OFF = 0
    HEAT = 1
    COOL = 2
    AUTO = 3
    AUXILIARY = 4
    RESUME_ON = 5
    FAN = 6
    FURNANCE = 7
    DRY = 8
    MOIST = 9
    AUTO_CHANGE_OVER = 10
    HEATING_ECON = 11
    COOLING_ECON = 12
    AWAY = 13
    FULL_POWER = 15
    MANUFACTURER_SPECIFIC = 31


MODE_SETPOINT_MAPPINGS = {
    ThermostatMode.OFF: (),
    ThermostatMode.HEAT: ("setpoint_heating",),
    ThermostatMode.COOL: ("setpoint_cooling",),
    ThermostatMode.AUTO: ("setpoint_heating", "setpoint_cooling"),
    ThermostatMode.AUXILIARY: ("setpoint_heating",),
    ThermostatMode.FURNANCE: ("setpoint_furnace",),
    ThermostatMode.DRY: ("setpoint_dry_air",),
    ThermostatMode.MOIST: ("setpoint_moist_air",),
    ThermostatMode.AUTO_CHANGE_OVER: ("setpoint_auto_changeover",),
    ThermostatMode.HEATING_ECON: ("setpoint_eco_heating",),
    ThermostatMode.COOLING_ECON: ("setpoint_eco_cooling",),
    ThermostatMode.AWAY: ("setpoint_away_heating", "setpoint_away_cooling"),
    ThermostatMode.FULL_POWER: ("setpoint_full_power",),
}


# strings, OZW and/or qt-ozw does not send numeric values
# https://github.com/OpenZWave/open-zwave/blob/master/cpp/src/command_classes/ThermostatOperatingState.cpp
HVAC_CURRENT_MAPPINGS = {
    "idle": CURRENT_HVAC_IDLE,
    "heat": CURRENT_HVAC_HEAT,
    "pending heat": CURRENT_HVAC_IDLE,
    "heating": CURRENT_HVAC_HEAT,
    "cool": CURRENT_HVAC_COOL,
    "pending cool": CURRENT_HVAC_IDLE,
    "cooling": CURRENT_HVAC_COOL,
    "fan only": CURRENT_HVAC_FAN,
    "vent / economiser": CURRENT_HVAC_FAN,
    "off": CURRENT_HVAC_OFF,
}


# Map Z-Wave HVAC Mode to Home Assistant value
ZW_HVAC_MODE_MAPPINGS = {
    ThermostatMode.OFF: HVAC_MODE_OFF,
    ThermostatMode.HEAT: HVAC_MODE_HEAT,
    ThermostatMode.COOL: HVAC_MODE_COOL,
    ThermostatMode.AUTO: HVAC_MODE_AUTO,
    ThermostatMode.AUXILIARY: HVAC_MODE_HEAT,
    ThermostatMode.FAN: HVAC_MODE_FAN_ONLY,
    ThermostatMode.FURNANCE: HVAC_MODE_HEAT,
    ThermostatMode.DRY: HVAC_MODE_DRY,
    ThermostatMode.AUTO_CHANGE_OVER: HVAC_MODE_HEAT_COOL,
    ThermostatMode.HEATING_ECON: HVAC_MODE_HEAT,
    ThermostatMode.COOLING_ECON: HVAC_MODE_COOL,
    ThermostatMode.AWAY: HVAC_MODE_HEAT_COOL,
    ThermostatMode.FULL_POWER: HVAC_MODE_HEAT,
}

# Map Home Assistant HVAC Mode to Z-Wave value
HVAC_MODE_ZW_MAPPINGS = {
    HVAC_MODE_OFF: ThermostatMode.OFF,
    HVAC_MODE_HEAT: ThermostatMode.HEAT,
    HVAC_MODE_COOL: ThermostatMode.COOL,
    HVAC_MODE_AUTO: ThermostatMode.AUTO,
    HVAC_MODE_FAN_ONLY: ThermostatMode.FAN,
    HVAC_MODE_DRY: ThermostatMode.DRY,
    HVAC_MODE_HEAT_COOL: ThermostatMode.AUTO_CHANGE_OVER,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Climate from Config Entry."""

    @callback
    def async_add_climate(values):
        """Add Z-Wave Climate."""
        async_add_entities([ZWaveClimateEntity(values)])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_{CLIMATE_DOMAIN}", async_add_climate
        )
    )


class ZWaveClimateEntity(ZWaveDeviceEntity, ClimateEntity):
    """Representation of a Z-Wave Climate device."""

    def __init__(self, values):
        """Initialize the entity."""
        super().__init__(values)
        self._current_mode_setpoint_values = self._get_current_mode_setpoint_values()

    @callback
    def on_value_update(self):
        """Call when the underlying value(s) is added or updated."""
        self._current_mode_setpoint_values = self._get_current_mode_setpoint_values()

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if not self.values.mode:
            return None
        return ZW_HVAC_MODE_MAPPINGS.get(
            self.values.mode.value[VALUE_SELECTED_ID], HVAC_MODE_AUTO
        )

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        if not self.values.mode:
            return []
        # Z-Wave uses one list for both modes and presets. Extract the unique modes
        all_modes = []
        for val in self.values.mode.value[VALUE_LIST]:
            hass_mode = ZW_HVAC_MODE_MAPPINGS.get(val[VALUE_ID])
            if hass_mode and hass_mode not in all_modes:
                all_modes.append(hass_mode)
        return all_modes

    @property
    def fan_mode(self):
        """Return the fan speed set."""
        return self.values.fan_mode.value[VALUE_SELECTED_LABEL]

    @property
    def fan_modes(self):
        """Return a list of available fan modes."""
        return [entry[VALUE_LABEL] for entry in self.values.fan_mode.value[VALUE_LIST]]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self.values.temperature and self.values.temperature.units == "F":
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if not self.values.temperature:
            return None
        return self.values.temperature.value

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        if not self.values.operating_state:
            return None
        cur_state = self.values.operating_state.value.lower()
        return HVAC_CURRENT_MAPPINGS.get(cur_state)

    @property
    def preset_mode(self):
        """Return preset operation ie. eco, away."""
        # Z-Wave uses mode-values > 10 for presets
        if self.values.mode.value[VALUE_SELECTED_ID] > 10:
            return self.values.mode.value[VALUE_SELECTED_LABEL]
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return the list of available preset operation modes."""
        # Z-Wave uses mode-values > 10 for presets
        return [PRESET_NONE] + [
            val[VALUE_LABEL]
            for val in self.values.mode.value[VALUE_LIST]
            if val[VALUE_ID] > 10
        ]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._current_mode_setpoint_values[0].value

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return self._current_mode_setpoint_values[0].value

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        return self._current_mode_setpoint_values[1].value

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature.

        Must know if single or double setpoint.
        """
        if len(self._current_mode_setpoint_values) == 1:
            setpoint = self._current_mode_setpoint_values[0]
            target_temp = kwargs.get(ATTR_TEMPERATURE)
            if setpoint is not None and target_temp is not None:
                setpoint.send_value(target_temp)
        elif len(self._current_mode_setpoint_values) == 2:
            (setpoint_low, setpoint_high) = self._current_mode_setpoint_values
            target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if setpoint_low is not None and target_temp_low is not None:
                setpoint_low.send_value(target_temp_low)
            if setpoint_high is not None and target_temp_high is not None:
                setpoint_high.send_value(target_temp_high)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        # get id for this fan_mode
        fan_mode_value = _get_list_id(self.values.fan_mode.value[VALUE_LIST], fan_mode)
        if fan_mode_value is None:
            _LOGGER.warning("Received an invalid fan mode: %s", fan_mode)
            return
        self.values.fan_mode.send_value(fan_mode_value)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if not self.values.mode:
            return
        if hvac_mode not in self.hvac_modes:
            _LOGGER.warning("Received an invalid hvac mode: %s", hvac_mode)
            return
        hvac_mode_value = HVAC_MODE_ZW_MAPPINGS.get(hvac_mode)
        self.values.mode.send_value(hvac_mode_value)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        if preset_mode == PRESET_NONE:
            # try to restore to the (translated) main hvac mode
            await self.async_set_hvac_mode(self.hvac_mode)
            return
        preset_mode_value = _get_list_id(
            self.values.mode.value[VALUE_LIST], preset_mode
        )
        if preset_mode_value is None:
            _LOGGER.warning("Received an invalid preset mode: %s", preset_mode)
            return
        self.values.mode.send_value(preset_mode_value)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        data = super().device_state_attributes
        if self.values.fan_action:
            data[ATTR_FAN_ACTION] = self.values.fan_action.value
        if self.values.valve_position:
            data[
                ATTR_VALVE_POSITION
            ] = f"{self.values.valve_position.value} {self.values.valve_position.units}"
        return data

    @property
    def supported_features(self):
        """Return the list of supported features."""
        support = 0
        if len(self._current_mode_setpoint_values) == 1:
            support |= SUPPORT_TARGET_TEMPERATURE
        if len(self._current_mode_setpoint_values) > 1:
            support |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if self.values.fan_mode:
            support |= SUPPORT_FAN_MODE
        if self.values.mode:
            support |= SUPPORT_PRESET_MODE
        return support

    def _get_current_mode_setpoint_values(self) -> Tuple:
        """Return a tuple of current setpoint Z-Wave value(s)."""
        current_mode = self.values.mode.value[VALUE_SELECTED_ID]
        setpoint_names = MODE_SETPOINT_MAPPINGS.get(current_mode, ())
        # we do not want None values in our tuple so check if the value exists
        return tuple(
            getattr(self.values, value_name)
            for value_name in setpoint_names
            if getattr(self.values, value_name, None)
        )


def _get_list_id(value_lst, value_lbl):
    """Return the id for the value in the list."""
    return next(
        (val[VALUE_ID] for val in value_lst if val[VALUE_LABEL] == value_lbl), None
    )
