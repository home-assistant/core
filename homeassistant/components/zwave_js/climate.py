"""Representation of Z-Wave thermostats."""
from __future__ import annotations

from typing import Any, Callable, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import (
    THERMOSTAT_CURRENT_TEMP_PROPERTY,
    THERMOSTAT_MODE_PROPERTY,
    THERMOSTAT_MODE_SETPOINT_MAP,
    THERMOSTAT_MODES,
    THERMOSTAT_OPERATING_STATE_PROPERTY,
    THERMOSTAT_SETPOINT_PROPERTY,
    CommandClass,
    ThermostatMode,
    ThermostatOperatingState,
    ThermostatSetpointType,
)
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
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

# Map Z-Wave HVAC Mode to Home Assistant value
# Note: We treat "auto" as "heat_cool" as most Z-Wave devices
# report auto_changeover as auto without schedule support.
ZW_HVAC_MODE_MAP: dict[int, str] = {
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

HVAC_CURRENT_MAP: dict[int, str] = {
    ThermostatOperatingState.IDLE: CURRENT_HVAC_IDLE,
    ThermostatOperatingState.PENDING_HEAT: CURRENT_HVAC_IDLE,
    ThermostatOperatingState.HEATING: CURRENT_HVAC_HEAT,
    ThermostatOperatingState.PENDING_COOL: CURRENT_HVAC_IDLE,
    ThermostatOperatingState.COOLING: CURRENT_HVAC_COOL,
    ThermostatOperatingState.FAN_ONLY: CURRENT_HVAC_FAN,
    ThermostatOperatingState.VENT_ECONOMIZER: CURRENT_HVAC_FAN,
    ThermostatOperatingState.AUX_HEATING: CURRENT_HVAC_HEAT,
    ThermostatOperatingState.SECOND_STAGE_HEATING: CURRENT_HVAC_HEAT,
    ThermostatOperatingState.SECOND_STAGE_COOLING: CURRENT_HVAC_COOL,
    ThermostatOperatingState.SECOND_STAGE_AUX_HEAT: CURRENT_HVAC_HEAT,
    ThermostatOperatingState.THIRD_STAGE_AUX_HEAT: CURRENT_HVAC_HEAT,
}

ATTR_FAN_STATE = "fan_state"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave climate from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_climate(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Climate."""
        entities: list[ZWaveBaseEntity] = []
        entities.append(ZWaveClimate(config_entry, client, info))

        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{CLIMATE_DOMAIN}",
            async_add_climate,
        )
    )


class ZWaveClimate(ZWaveBaseEntity, ClimateEntity):
    """Representation of a Z-Wave climate."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize lock."""
        super().__init__(config_entry, client, info)
        self._hvac_modes: dict[str, int | None] = {}
        self._hvac_presets: dict[str, int | None] = {}
        self._unit_value: ZwaveValue | None = None

        self._current_mode = self.get_zwave_value(
            THERMOSTAT_MODE_PROPERTY, command_class=CommandClass.THERMOSTAT_MODE
        )
        self._setpoint_values: dict[ThermostatSetpointType, ZwaveValue] = {}
        for enum in ThermostatSetpointType:
            self._setpoint_values[enum] = self.get_zwave_value(
                THERMOSTAT_SETPOINT_PROPERTY,
                command_class=CommandClass.THERMOSTAT_SETPOINT,
                value_property_key=enum.value,
                add_to_watched_value_ids=True,
            )
            # Use the first found non N/A setpoint value to always determine the
            # temperature unit
            if (
                not self._unit_value
                and enum != ThermostatSetpointType.NA
                and self._setpoint_values[enum]
            ):
                self._unit_value = self._setpoint_values[enum]
        self._operating_state = self.get_zwave_value(
            THERMOSTAT_OPERATING_STATE_PROPERTY,
            command_class=CommandClass.THERMOSTAT_OPERATING_STATE,
            add_to_watched_value_ids=True,
        )
        self._current_temp = self.get_zwave_value(
            THERMOSTAT_CURRENT_TEMP_PROPERTY,
            command_class=CommandClass.SENSOR_MULTILEVEL,
            add_to_watched_value_ids=True,
            check_all_endpoints=True,
        )
        if not self._unit_value:
            self._unit_value = self._current_temp
        self._current_humidity = self.get_zwave_value(
            "Humidity",
            command_class=CommandClass.SENSOR_MULTILEVEL,
            add_to_watched_value_ids=True,
            check_all_endpoints=True,
        )
        self._fan_mode = self.get_zwave_value(
            THERMOSTAT_MODE_PROPERTY,
            CommandClass.THERMOSTAT_FAN_MODE,
            add_to_watched_value_ids=True,
        )
        self._fan_state = self.get_zwave_value(
            THERMOSTAT_OPERATING_STATE_PROPERTY,
            CommandClass.THERMOSTAT_FAN_STATE,
            add_to_watched_value_ids=True,
        )
        self._set_modes_and_presets()
        self._supported_features = 0
        if len(self._hvac_presets) > 1:
            self._supported_features |= SUPPORT_PRESET_MODE
        # If any setpoint value exists, we can assume temperature
        # can be set
        if any(self._setpoint_values.values()):
            self._supported_features |= SUPPORT_TARGET_TEMPERATURE
        if HVAC_MODE_HEAT_COOL in self.hvac_modes:
            self._supported_features |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if self._fan_mode:
            self._supported_features |= SUPPORT_FAN_MODE

    def _setpoint_value(self, setpoint_type: ThermostatSetpointType) -> ZwaveValue:
        """Optionally return a ZwaveValue for a setpoint."""
        val = self._setpoint_values[setpoint_type]
        if val is None:
            raise ValueError("Value requested is not available")

        return val

    def _set_modes_and_presets(self) -> None:
        """Convert Z-Wave Thermostat modes into Home Assistant modes and presets."""
        all_modes: dict[str, int | None] = {}
        all_presets: dict[str, int | None] = {PRESET_NONE: None}

        # Z-Wave uses one list for both modes and presets.
        # Iterate over all Z-Wave ThermostatModes and extract the hvac modes and presets.
        if self._current_mode is None:
            self._hvac_modes = {
                ZW_HVAC_MODE_MAP[ThermostatMode.HEAT]: ThermostatMode.HEAT
            }
            return
        for mode_id, mode_name in self._current_mode.metadata.states.items():
            mode_id = int(mode_id)
            if mode_id in THERMOSTAT_MODES:
                # treat value as hvac mode
                hass_mode = ZW_HVAC_MODE_MAP.get(mode_id)
                if hass_mode:
                    all_modes[hass_mode] = mode_id
            else:
                # treat value as hvac preset
                all_presets[mode_name] = mode_id
        self._hvac_modes = all_modes
        self._hvac_presets = all_presets

    @property
    def _current_mode_setpoint_enums(self) -> list[ThermostatSetpointType | None]:
        """Return the list of enums that are relevant to the current thermostat mode."""
        if self._current_mode is None:
            # Thermostat(valve) with no support for setting a mode is considered heating-only
            return [ThermostatSetpointType.HEATING]
        return THERMOSTAT_MODE_SETPOINT_MAP.get(int(self._current_mode.value), [])  # type: ignore

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        if (
            self._unit_value
            and self._unit_value.metadata.unit
            and "f" in self._unit_value.metadata.unit.lower()
        ):
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def precision(self) -> float:
        """Return the precision of 0.1."""
        return PRECISION_TENTHS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        if self._current_mode is None:
            # Thermostat(valve) with no support for setting a mode is considered heating-only
            return HVAC_MODE_HEAT
        if self._current_mode.value is None:
            # guard missing value
            return HVAC_MODE_HEAT
        return ZW_HVAC_MODE_MAP.get(int(self._current_mode.value), HVAC_MODE_HEAT_COOL)

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return list(self._hvac_modes)

    @property
    def hvac_action(self) -> str | None:
        """Return the current running hvac operation if supported."""
        if not self._operating_state:
            return None
        if self._operating_state.value is None:
            # guard missing value
            return None
        return HVAC_CURRENT_MAP.get(int(self._operating_state.value))

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity level."""
        return self._current_humidity.value if self._current_humidity else None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp.value if self._current_temp else None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._current_mode and self._current_mode.value is None:
            # guard missing value
            return None
        try:
            temp = self._setpoint_value(self._current_mode_setpoint_enums[0])
        except (IndexError, ValueError):
            return None
        return temp.value if temp else None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        if self._current_mode and self._current_mode.value is None:
            # guard missing value
            return None
        try:
            temp = self._setpoint_value(self._current_mode_setpoint_enums[1])
        except (IndexError, ValueError):
            return None
        return temp.value if temp else None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        if self._current_mode and self._current_mode.value is None:
            # guard missing value
            return None
        if len(self._current_mode_setpoint_enums) > 1:
            return self.target_temperature
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._current_mode and self._current_mode.value is None:
            # guard missing value
            return None
        if self._current_mode and int(self._current_mode.value) not in THERMOSTAT_MODES:
            return_val: str = self._current_mode.metadata.states.get(
                str(self._current_mode.value)
            )
            return return_val
        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return list(self._hvac_presets)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if (
            self._fan_mode
            and self._fan_mode.value is not None
            and str(self._fan_mode.value) in self._fan_mode.metadata.states
        ):
            return cast(str, self._fan_mode.metadata.states[str(self._fan_mode.value)])
        return None

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        if self._fan_mode and self._fan_mode.metadata.states:
            return list(self._fan_mode.metadata.states.values())
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the optional state attributes."""
        if (
            self._fan_state
            and self._fan_state.value is not None
            and str(self._fan_state.value) in self._fan_state.metadata.states
        ):
            return {
                ATTR_FAN_STATE: self._fan_state.metadata.states[
                    str(self._fan_state.value)
                ]
            }

        return None

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._supported_features

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if not self._fan_mode:
            return

        try:
            new_state = int(
                next(
                    state
                    for state, label in self._fan_mode.metadata.states.items()
                    if label == fan_mode
                )
            )
        except StopIteration:
            raise ValueError(f"Received an invalid fan mode: {fan_mode}") from None

        await self.info.node.async_set_value(self._fan_mode, new_state)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        hvac_mode: str | None = kwargs.get(ATTR_HVAC_MODE)

        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if len(self._current_mode_setpoint_enums) == 1:
            setpoint: ZwaveValue = self._setpoint_value(
                self._current_mode_setpoint_enums[0]
            )
            target_temp: float | None = kwargs.get(ATTR_TEMPERATURE)
            if target_temp is not None:
                await self.info.node.async_set_value(setpoint, target_temp)
        elif len(self._current_mode_setpoint_enums) == 2:
            setpoint_low: ZwaveValue = self._setpoint_value(
                self._current_mode_setpoint_enums[0]
            )
            setpoint_high: ZwaveValue = self._setpoint_value(
                self._current_mode_setpoint_enums[1]
            )
            target_temp_low: float | None = kwargs.get(ATTR_TARGET_TEMP_LOW)
            target_temp_high: float | None = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if target_temp_low is not None:
                await self.info.node.async_set_value(setpoint_low, target_temp_low)
            if target_temp_high is not None:
                await self.info.node.async_set_value(setpoint_high, target_temp_high)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if not self._current_mode:
            # Thermostat(valve) with no support for setting a mode
            raise ValueError(
                f"Thermostat {self.entity_id} does not support setting a mode"
            )
        hvac_mode_value = self._hvac_modes.get(hvac_mode)
        if hvac_mode_value is None:
            raise ValueError(f"Received an invalid hvac mode: {hvac_mode}")
        await self.info.node.async_set_value(self._current_mode, hvac_mode_value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode == PRESET_NONE:
            # try to restore to the (translated) main hvac mode
            await self.async_set_hvac_mode(self.hvac_mode)
            return
        preset_mode_value = self._hvac_presets.get(preset_mode)
        if preset_mode_value is None:
            raise ValueError(f"Received an invalid preset mode: {preset_mode}")
        await self.info.node.async_set_value(self._current_mode, preset_mode_value)
