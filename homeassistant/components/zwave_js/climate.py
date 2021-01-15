"""Representation of Z-Wave locks."""
from enum import IntEnum
import logging
from typing import Any, Callable, Dict, List, Optional

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

_LOGGER = logging.getLogger(__name__)


class ThermostatMode(IntEnum):
    """Enum with all (known/used) Z-Wave ThermostatModes."""

    # https://github.com/zwave-js/node-zwave-js/blob/master/packages/zwave-js/src/lib/commandclass/ThermostatModeCC.ts#L53-L70
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


# In Z-Wave the modes and presets are both in ThermostatMode.
# This list contains thermostatmodes we should consider a mode only
MODES_LIST = [
    ThermostatMode.OFF,
    ThermostatMode.HEAT,
    ThermostatMode.COOL,
    ThermostatMode.AUTO,
    ThermostatMode.AUTO_CHANGE_OVER,
]

# https://github.com/zwave-js/node-zwave-js/blob/master/packages/zwave-js/src/lib/commandclass/ThermostatSetpointCC.ts#L53-L66
MODE_SETPOINT_MAP: Dict[int, List[str]] = {
    ThermostatMode.OFF: [],
    ThermostatMode.HEAT: ["Heating"],
    ThermostatMode.COOL: ["Cooling"],
    ThermostatMode.AUTO: ["Heating", "Cooling"],
    ThermostatMode.AUXILIARY: ["Heating"],
    ThermostatMode.FURNANCE: ["Furnace"],
    ThermostatMode.DRY: ["Dry Air"],
    ThermostatMode.MOIST: ["Moist Air"],
    ThermostatMode.AUTO_CHANGE_OVER: ["Auto Changeover"],
    ThermostatMode.HEATING_ECON: ["Energy Save Heating"],
    ThermostatMode.COOLING_ECON: ["Energy Save Cooling"],
    ThermostatMode.AWAY: ["Away Heating", "Away Cooling"],
    ThermostatMode.FULL_POWER: ["Full Power"],
}

# Map Z-Wave HVAC Mode to Home Assistant value
# Note: We treat "auto" as "heat_cool" as most Z-Wave devices
# report auto_changeover as auto without schedule support.
ZW_HVAC_MODE_MAP: Dict[int, str] = {
    ThermostatMode.OFF: HVAC_MODE_OFF,
    ThermostatMode.HEAT: HVAC_MODE_HEAT,
    ThermostatMode.COOL: HVAC_MODE_COOL,
    # Z-Wave auto mode is actually heat/cool in the hass world
    ThermostatMode.AUTO: HVAC_MODE_HEAT_COOL,
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

ZWAVE_SETPOINT_PROPERTY = "setpoint"


class OperatingMode(IntEnum):
    """Enum with all (known/used) Z-Wave OperatingModes."""

    # https://github.com/zwave-js/node-zwave-js/blob/master/packages/zwave-js/src/lib/commandclass/ThermostatOperatingStateCC.ts#L38-L51
    IDLE = 0
    HEATING = 1
    COOLING = 2
    FAN_ONLY = 3
    PENDING_HEAT = 4
    PENDING_COOL = 5
    VENT_ECONOMIZER = 6
    AUX_HEATING = 7
    SECOND_STAGE_HEATING = 8
    SECOND_STAGE_COOLING = 9
    SECOND_STAGE_AUX_HEAT = 10
    THIRD_STAGE_AUX_HEAT = 11


HVAC_CURRENT_MAP: Dict[int, str] = {
    OperatingMode.IDLE: CURRENT_HVAC_IDLE,
    OperatingMode.PENDING_HEAT: CURRENT_HVAC_IDLE,
    OperatingMode.HEATING: CURRENT_HVAC_HEAT,
    OperatingMode.PENDING_COOL: CURRENT_HVAC_IDLE,
    OperatingMode.COOLING: CURRENT_HVAC_COOL,
    OperatingMode.FAN_ONLY: CURRENT_HVAC_FAN,
    OperatingMode.VENT_ECONOMIZER: CURRENT_HVAC_FAN,
    # not defined in ozw integration but we will provide them anyway
    OperatingMode.AUX_HEATING: CURRENT_HVAC_HEAT,
    OperatingMode.SECOND_STAGE_HEATING: CURRENT_HVAC_HEAT,
    OperatingMode.SECOND_STAGE_COOLING: CURRENT_HVAC_COOL,
    OperatingMode.SECOND_STAGE_AUX_HEAT: CURRENT_HVAC_HEAT,
    OperatingMode.THIRD_STAGE_AUX_HEAT: CURRENT_HVAC_HEAT,
}


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave climate from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_climate(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Climate."""
        entities: List[ZWaveBaseEntity] = []
        entities.append(ZWaveClimate(client, info))

        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_add_{CLIMATE_DOMAIN}", async_add_climate
        )
    )


class ZWaveClimate(ZWaveBaseEntity, ClimateEntity):
    """Representation of a Z-Wave climate."""

    def __init__(self, client: ZwaveClient, info: ZwaveDiscoveryInfo) -> None:
        """Initialize lock."""
        super().__init__(client, info)
        self._hvac_modes: Dict[str, Optional[int]] = {}
        self._hvac_presets: Dict[str, Optional[int]] = {}
        self.on_value_update()

    @callback
    def on_value_update(self) -> None:
        """Call when a watched value is added or updated."""
        self._current_mode_setpoint_values = self._get_current_mode_setpoint_values()
        if not self._hvac_modes:
            self._set_modes_and_presets()

    def _get_current_mode_setpoint_values(self) -> List[ZwaveValue]:
        """Return a list of current setpoint Z-Wave value(s)."""
        setpoint_keys: List[str]
        if not self.info.primary_value:
            setpoint_keys = ["Heating"]
        else:
            current_mode = int(self.info.primary_value.value)
            setpoint_keys = MODE_SETPOINT_MAP.get(current_mode, [])
        # we do not want None values in our list so check if the value exists
        return [
            self.get_zwave_value(
                ZWAVE_SETPOINT_PROPERTY,
                CommandClass.THERMOSTAT_SETPOINT,
                value_property_key_name=key,
                add_to_watched_value_ids=True,
            )
            for key in setpoint_keys
            if self.get_zwave_value(
                ZWAVE_SETPOINT_PROPERTY,
                CommandClass.THERMOSTAT_SETPOINT,
                value_property_key_name=key,
                add_to_watched_value_ids=True,
            )
        ]

    def _set_modes_and_presets(self) -> None:
        """Convert Z-Wave Thermostat modes into Home Assistant modes and presets."""
        all_modes: Dict[str, Optional[int]] = {}
        all_presets: Dict[str, Optional[int]] = {PRESET_NONE: None}
        if self.info.primary_value:
            # Z-Wave uses one list for both modes and presets.
            # Iterate over all Z-Wave ThermostatModes and extract the hvac modes and presets.
            for id, mode in self.info.primary_value.metadata.states.items():
                id = int(id)
                if id in MODES_LIST:
                    # treat value as hvac mode
                    hass_mode = ZW_HVAC_MODE_MAP.get(id)
                    if hass_mode:
                        all_modes[hass_mode] = id
                else:
                    # treat value as hvac preset
                    all_presets[mode] = id
        else:
            all_modes[HVAC_MODE_HEAT] = None
        self._hvac_modes = all_modes
        self._hvac_presets = all_presets

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        temp: ZwaveValue = (
            self._current_mode_setpoint_values[0]
            if self._current_mode_setpoint_values
            else None
        )
        if temp is not None and temp.metadata.unit == "°F":
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        if not self.info.primary_value:
            # Thermostat(valve) with no support for setting a mode is considered heating-only
            return HVAC_MODE_HEAT
        return ZW_HVAC_MODE_MAP.get(
            int(self.info.primary_value.value), HVAC_MODE_HEAT_COOL
        )

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return list(self._hvac_modes)

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        operating_state = self.get_zwave_value(
            "state",
            command_class=CommandClass.THERMOSTAT_OPERATING_STATE,
            add_to_watched_value_ids=True,
        )
        if not operating_state:
            return None
        return HVAC_CURRENT_MAP.get(int(operating_state.value))

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        temp = self.get_zwave_value(
            "Air temperature",
            command_class=CommandClass.SENSOR_MULTILEVEL,
            add_to_watched_value_ids=True,
        )
        if not temp:
            return None
        return float(temp.value)

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return float(self._current_mode_setpoint_values[0].value)

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        if len(self._current_mode_setpoint_values) < 2:
            return None
        return float(self._current_mode_setpoint_values[1].value)

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return float(self._current_mode_setpoint_values[0].value)

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        # A Zwave mode that can not be translated to a hass mode is considered a preset
        if not self.info.primary_value:
            return None
        if int(self.info.primary_value.value) not in MODES_LIST:
            return_val: str = self.info.primary_value.metadata.states.get(
                self.info.primary_value.value
            )
            return return_val
        return PRESET_NONE

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return list(self._hvac_presets)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        hvac_mode: Optional[str] = kwargs.get(ATTR_HVAC_MODE)

        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

        if len(self._current_mode_setpoint_values) == 1:
            setpoint: ZwaveValue = self._current_mode_setpoint_values[0]
            target_temp = kwargs.get(ATTR_TEMPERATURE)
            if setpoint is not None and target_temp is not None:
                await self.info.node.async_set_value(setpoint, target_temp)
        elif len(self._current_mode_setpoint_values) == 2:
            setpoint_low: ZwaveValue = self._current_mode_setpoint_values[0]
            setpoint_high: ZwaveValue = self._current_mode_setpoint_values[1]
            target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if setpoint_low is not None and target_temp_low is not None:
                await self.info.node.async_set_value(setpoint_low, target_temp_low)
            if setpoint_high is not None and target_temp_high is not None:
                await self.info.node.async_set_value(setpoint_high, target_temp_high)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if not self.info.primary_value:
            # Thermostat(valve) with no support for setting a mode
            _LOGGER.warning(
                "Thermostat %s does not support setting a mode", self.entity_id
            )
            return
        hvac_mode_value = self._hvac_modes.get(hvac_mode)
        if hvac_mode_value is None:
            _LOGGER.warning("Received an invalid hvac mode: %s", hvac_mode)
            return
        await self.info.node.async_set_value(self.info.primary_value, hvac_mode_value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode == PRESET_NONE:
            # try to restore to the (translated) main hvac mode
            await self.async_set_hvac_mode(self.hvac_mode)
            return
        preset_mode_value = self._hvac_presets.get(preset_mode)
        if preset_mode_value is None:
            _LOGGER.warning("Received an invalid preset mode: %s", preset_mode)
            return
        await self.info.node.async_set_value(self.info.primary_value, preset_mode_value)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        support = 0
        if len(self._current_mode_setpoint_values) == 1:
            support |= SUPPORT_TARGET_TEMPERATURE
        if len(self._current_mode_setpoint_values) > 1:
            support |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if self.hvac_mode:
            support |= SUPPORT_PRESET_MODE
        return support
