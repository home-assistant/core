"""Support for Z-Wave climate devices."""
from enum import IntEnum
from typing import Optional, Tuple

from openzwavemqtt.const import CommandClass

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
    PRESET_AWAY,
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
VALUE_SELECTED = "Selected_id"

ATTR_FAN_ACTION = "fan_action"


class ThermostatMode(IntEnum):
    """Enum with all (known/used) Z-Wave ThermostatModes."""

    # https://github.com/OpenZWave/open-zwave/blob/master/cpp/src/command_classes/ThermostatMode.cpp
    OFF = 0
    HEAT = 1
    COOl = 2
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
    FULL_POWER = 14


MODE_SETPOINT_MAPPINGS = {
    ThermostatMode.OFF: (),
    ThermostatMode.HEAT: ("setpoint_heating",),
    ThermostatMode.COOl: ("setpoint_cooling",),
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

DEFAULT_HVAC_MODES = [
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
]

# Map Z-Wave HVAC Mode to Home Assistant value
ZW_HVAC_MODE_MAPPINGS = {
    0x00: HVAC_MODE_OFF,
    0x01: HVAC_MODE_HEAT,
    0x02: HVAC_MODE_COOL,
    0x03: HVAC_MODE_AUTO,
    0x04: HVAC_MODE_HEAT,
    0x06: HVAC_MODE_FAN_ONLY,
    0x07: HVAC_MODE_HEAT,
    0x08: HVAC_MODE_DRY,
    0x0A: HVAC_MODE_HEAT_COOL,
    0x0B: HVAC_MODE_HEAT,
    0x0C: HVAC_MODE_COOL,
    0x0D: HVAC_MODE_HEAT_COOL,
    0x0F: HVAC_MODE_HEAT_COOL,
}

# Map Home Assistant HVAC Mode to Z-Wave value
HVAC_MODE_ZW_MAPPINGS = {
    HVAC_MODE_OFF: 0x00,
    HVAC_MODE_HEAT: 0x01,
    HVAC_MODE_COOL: 0x02,
    HVAC_MODE_AUTO: 0x03,
    HVAC_MODE_FAN_ONLY: 0x06,
    HVAC_MODE_DRY: 0x08,
    HVAC_MODE_HEAT_COOL: 0x0A,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Climate from Config Entry."""

    @callback
    def async_add_climate(values):
        """Add Z-Wave Climate."""
        climate = None
        if values.primary.command_class == CommandClass.THERMOSTAT_SETPOINT:
            climate = ZWaveClimateSingleSetpoint(values)
        elif values.primary.command_class == CommandClass.THERMOSTAT_MODE:
            climate = ZWaveClimateMultipleSetpoint(values)

        if climate is not None:
            async_add_entities([climate])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_{CLIMATE_DOMAIN}", async_add_climate
        )
    )


class ZWaveClimateBase(ZWaveDeviceEntity, ClimateEntity):
    """Representation of a Z-Wave Climate device."""

    def __init__(self, values):
        """Initialize the Z-Wave climate device."""
        super().__init__(values)
        self._target_temperature = None
        self._target_temperature_range = (None, None)
        self._current_temperature = None
        self._hvac_action = None
        self._hvac_list = None
        self._zw_hvac_mode = None
        self._default_hvac_mode = None
        self._preset_list = None
        self._preset_mode = None
        self._current_fan_mode = None
        self._fan_modes = None
        self._fan_action = None
        self._unit = None
        self.update_properties()

    @callback
    def on_value_update(self):
        """Update after value change."""
        self.update_properties()

    def _mode(self) -> None:
        """Return thermostat mode Z-Wave value."""
        raise NotImplementedError()

    def _current_mode_setpoints(self) -> Tuple:
        """Return a tuple of current setpoint Z-Wave value(s)."""
        raise NotImplementedError()

    def update_properties(self):
        """Handle the data changes for node values."""
        self._update_operation_mode()
        self._update_current_temp()
        self._update_fan_mode()
        self._update_target_temp()
        self._update_operating_state()
        self._update_fan_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        support = SUPPORT_TARGET_TEMPERATURE
        if self._hvac_list and HVAC_MODE_HEAT_COOL in self._hvac_list:
            support |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if self._preset_list and PRESET_AWAY in self._preset_list:
            support |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if len(self._current_mode_setpoints()) > 1:
            support |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if self.values.fan_mode:
            support |= SUPPORT_FAN_MODE
        if self._preset_list:
            support |= SUPPORT_PRESET_MODE
        return support

    def _update_operation_mode(self):
        """Update hvac and preset modes."""
        if not self._mode():
            return
        self._hvac_list = []
        self._preset_list = []
        self._hvac_value_label_mapping = {}
        self._hvac_label_value_mapping = {}
        values_list = self._mode().value[VALUE_LIST]
        mode_values = [value[VALUE_ID] for value in values_list]
        for value in mode_values:
            ha_mode = ZW_HVAC_MODE_MAPPINGS.get(value)
            if ha_mode is not None and ha_mode not in self._hvac_list:
                self._hvac_list.append(ha_mode)
            else:
                self._preset_list.append(value)
            label = next(
                entry[VALUE_LABEL] for entry in values_list if value == entry[VALUE_ID]
            )
            self._hvac_value_label_mapping[value] = label
            self._hvac_label_value_mapping[label.lower()] = value

        for mode in DEFAULT_HVAC_MODES:
            if mode in self._hvac_list:
                self._default_hvac_mode = mode
                break

        current_mode_value = self._mode().value[VALUE_SELECTED]
        if current_mode_value in ZW_HVAC_MODE_MAPPINGS:
            self._zw_hvac_mode = current_mode_value
            self._preset_mode = PRESET_NONE
        else:
            current_mode_label = self._hvac_value_label_mapping[current_mode_value]
            if (
                "heat" in current_mode_label.lower()
                and HVAC_MODE_HEAT in self._hvac_list
            ):
                self._zw_hvac_mode = HVAC_MODE_ZW_MAPPINGS[HVAC_MODE_HEAT]
            elif (
                "cool" in current_mode_label.lower()
                and HVAC_MODE_COOL in self._hvac_list
            ):
                self._zw_hvac_mode = HVAC_MODE_ZW_MAPPINGS[HVAC_MODE_COOL]
            else:
                self._zw_hvac_mode = self._default_hvac_mode
            self._preset_mode = current_mode_value

    def _update_current_temp(self):
        """Update current temperature."""
        if not self.values.temperature:
            return
        self._current_temperature = self.values.temperature.value
        device_unit = self.values.temperature.units
        if device_unit is not None:
            self._unit = device_unit

    def _update_fan_mode(self):
        """Update fan mode."""
        if not self.values.fan_mode:
            return
        self._fan_value_label_mapping = {}
        self._fan_label_value_mapping = {}
        self._fan_modes = []
        for entry in self.values.fan_mode.value[VALUE_LIST]:
            self._fan_value_label_mapping[entry[VALUE_ID]] = entry[VALUE_LABEL]
            self._fan_label_value_mapping[entry[VALUE_LABEL]] = entry[VALUE_ID]
            self._fan_modes.append(entry[VALUE_ID])
        self._current_fan_mode = self.values.fan_mode.value[VALUE_SELECTED]

    def _update_target_temp(self):
        """Update target temperature."""
        current_setpoints = self._current_mode_setpoints()
        self._target_temperature = None
        self._target_temperature_range = (None, None)
        if len(current_setpoints) == 1:
            setpoint = current_setpoints[0]
            if setpoint is not None:
                self._target_temperature = round((float(setpoint.value)), 1)
        elif len(current_setpoints) == 2:
            (setpoint_low, setpoint_high) = current_setpoints
            target_low, target_high = None, None
            if setpoint_low is not None:
                target_low = round((float(setpoint_low.value)), 1)
            if setpoint_high is not None:
                target_high = round((float(setpoint_high.value)), 1)
            self._target_temperature_range = (target_low, target_high)

    def _update_operating_state(self):
        """Update operating state."""
        if not self.values.operating_state:
            return
        mode = self.values.operating_state.value
        self._hvac_action = HVAC_CURRENT_MAPPINGS.get(str(mode).lower())

    def _update_fan_state(self):
        """Update fan state."""
        if not self.values.fan_action:
            return
        self._fan_action = self.values.fan_action.value

    @property
    def fan_mode(self):
        """Return the fan speed set."""
        if self._current_fan_mode is None:
            return None
        return self._fan_value_label_mapping[self._current_fan_mode]

    @property
    def fan_modes(self):
        """Return a list of available fan modes."""
        if not self._fan_modes:
            return None
        fan_mode_labels = []
        for mode_value in self._fan_modes:
            fan_mode_labels.append(self._fan_value_label_mapping[mode_value])
        return fan_mode_labels

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._unit == "F":
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Needs to be one of HVAC_MODE_*.
        """
        if not self._mode():
            return self._default_hvac_mode
        return ZW_HVAC_MODE_MAPPINGS[self._zw_hvac_mode]

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        if not self._mode():
            return []
        return self._hvac_list

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Needs to be one of CURRENT_HVAC_*.
        """
        return self._hvac_action

    @property
    def preset_mode(self):
        """Return preset operation ie. eco, away.

        Needs to be one of PRESET_*.
        """
        if not self._mode() or self._preset_mode == PRESET_NONE:
            return PRESET_NONE
        return self._hvac_value_label_mapping[self._preset_mode]

    @property
    def preset_modes(self):
        """Return the list of available preset operation modes.

        Need to be a subset of PRESET_MODES.
        """
        if not self._mode():
            return []
        preset_labels = []
        for value in self._preset_list:
            preset_labels.append(self._hvac_value_label_mapping[value])
        preset_labels.append(PRESET_NONE)
        return preset_labels

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return self._target_temperature_range[0]

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        return self._target_temperature_range[1]

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature.

        Must know if single or double setpoint.
        """
        current_setpoints = self._current_mode_setpoints()
        if len(current_setpoints) == 1:
            setpoint = current_setpoints[0]
            target_temp = kwargs.get(ATTR_TEMPERATURE)
            if setpoint is not None and target_temp is not None:
                setpoint.send_value(target_temp)
        elif len(current_setpoints) == 2:
            (setpoint_low, setpoint_high) = current_setpoints
            target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if setpoint_low is not None and target_temp_low is not None:
                setpoint_low.send_value(target_temp_low)
            if setpoint_high is not None and target_temp_high is not None:
                setpoint_high.send_value(target_temp_high)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if not self.values.fan_mode:
            return
        fan_mode_value = self._fan_label_value_mapping[fan_mode]
        self.values.fan_mode.send_value(fan_mode_value)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if not self._mode():
            return
        hvac_mode_value = HVAC_MODE_ZW_MAPPINGS[hvac_mode]
        self._preset_mode = PRESET_NONE
        self._mode().send_value(hvac_mode_value)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        if not self._mode():
            return
        if preset_mode == PRESET_NONE:
            self._mode().send_value(self._zw_hvac_mode)
        else:
            preset_mode_value = self._hvac_label_value_mapping[preset_mode.lower()]
            self._mode().send_value(preset_mode_value)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        data = super().device_state_attributes
        if self._fan_action:
            data[ATTR_FAN_ACTION] = self._fan_action
        return data


class ZWaveClimateSingleSetpoint(ZWaveClimateBase):
    """Representation of a single setpoint Z-Wave thermostat device."""

    def _mode(self) -> None:
        """Return thermostat mode Z-Wave value."""
        return self.values.mode

    def _current_mode_setpoints(self) -> Tuple:
        """Return a tuple of current setpoint Z-Wave value(s)."""
        return (self.values.primary,)


class ZWaveClimateMultipleSetpoint(ZWaveClimateBase):
    """Representation of a multiple setpoint Z-Wave thermostat device."""

    def _mode(self) -> None:
        """Return thermostat mode Z-Wave value."""
        return self.values.primary

    def _current_mode_setpoints(self) -> Tuple:
        """Return a tuple of current setpoint Z-Wave value(s)."""
        current_mode = self.values.primary.value["Selected_id"]
        setpoints_names = MODE_SETPOINT_MAPPINGS.get(current_mode, ())
        return tuple(getattr(self.values, name, None) for name in setpoints_names)
