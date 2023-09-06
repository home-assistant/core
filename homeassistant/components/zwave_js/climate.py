"""Representation of Z-Wave thermostats."""
from __future__ import annotations

from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.thermostat import (
    THERMOSTAT_CURRENT_TEMP_PROPERTY,
    THERMOSTAT_HUMIDITY_PROPERTY,
    THERMOSTAT_MODE_PROPERTY,
    THERMOSTAT_MODE_SETPOINT_MAP,
    THERMOSTAT_OPERATING_STATE_PROPERTY,
    THERMOSTAT_SETPOINT_PROPERTY,
    ThermostatMode,
    ThermostatOperatingState,
    ThermostatSetpointType,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DATA_CLIENT, DOMAIN, LOGGER
from .discovery import ZwaveDiscoveryInfo
from .discovery_data_template import DynamicCurrentTempClimateDataTemplate
from .entity import ZWaveBaseEntity
from .helpers import get_value_of_zwave_value

PARALLEL_UPDATES = 0

THERMOSTAT_MODES = [
    ThermostatMode.OFF,
    ThermostatMode.HEAT,
    ThermostatMode.COOL,
    ThermostatMode.AUTO,
    ThermostatMode.AUTO_CHANGE_OVER,
    ThermostatMode.FAN,
    ThermostatMode.DRY,
]

# Map Z-Wave HVAC Mode to Home Assistant value
# Note: We treat "auto" as "heat_cool" as most Z-Wave devices
# report auto_changeover as auto without schedule support.
ZW_HVAC_MODE_MAP: dict[int, HVACMode] = {
    ThermostatMode.OFF: HVACMode.OFF,
    ThermostatMode.HEAT: HVACMode.HEAT,
    ThermostatMode.COOL: HVACMode.COOL,
    # Z-Wave auto mode is actually heat/cool in the hass world
    ThermostatMode.AUTO: HVACMode.HEAT_COOL,
    ThermostatMode.AUXILIARY: HVACMode.HEAT,
    ThermostatMode.FAN: HVACMode.FAN_ONLY,
    ThermostatMode.FURNACE: HVACMode.HEAT,
    ThermostatMode.DRY: HVACMode.DRY,
    ThermostatMode.AUTO_CHANGE_OVER: HVACMode.HEAT_COOL,
    ThermostatMode.HEATING_ECON: HVACMode.HEAT,
    ThermostatMode.COOLING_ECON: HVACMode.COOL,
    ThermostatMode.AWAY: HVACMode.HEAT_COOL,
    ThermostatMode.FULL_POWER: HVACMode.HEAT,
}

HVAC_CURRENT_MAP: dict[int, HVACAction] = {
    ThermostatOperatingState.IDLE: HVACAction.IDLE,
    ThermostatOperatingState.PENDING_HEAT: HVACAction.IDLE,
    ThermostatOperatingState.HEATING: HVACAction.HEATING,
    ThermostatOperatingState.PENDING_COOL: HVACAction.IDLE,
    ThermostatOperatingState.COOLING: HVACAction.COOLING,
    ThermostatOperatingState.FAN_ONLY: HVACAction.FAN,
    ThermostatOperatingState.VENT_ECONOMIZER: HVACAction.FAN,
    ThermostatOperatingState.AUX_HEATING: HVACAction.HEATING,
    ThermostatOperatingState.SECOND_STAGE_HEATING: HVACAction.HEATING,
    ThermostatOperatingState.SECOND_STAGE_COOLING: HVACAction.COOLING,
    ThermostatOperatingState.SECOND_STAGE_AUX_HEAT: HVACAction.HEATING,
    ThermostatOperatingState.THIRD_STAGE_AUX_HEAT: HVACAction.HEATING,
}

ATTR_FAN_STATE = "fan_state"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave climate from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_climate(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Climate."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "dynamic_current_temp":
            entities.append(DynamicCurrentTempClimate(config_entry, driver, info))
        else:
            entities.append(ZWaveClimate(config_entry, driver, info))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{CLIMATE_DOMAIN}",
            async_add_climate,
        )
    )


class ZWaveClimate(ZWaveBaseEntity, ClimateEntity):
    """Representation of a Z-Wave climate."""

    _attr_precision = PRECISION_TENTHS

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize thermostat."""
        super().__init__(config_entry, driver, info)
        self._hvac_modes: dict[HVACMode, int | None] = {}
        self._hvac_presets: dict[str, int | None] = {}
        self._unit_value: ZwaveValue | None = None

        self._current_mode = self.get_zwave_value(
            THERMOSTAT_MODE_PROPERTY, command_class=CommandClass.THERMOSTAT_MODE
        )
        self._setpoint_values: dict[ThermostatSetpointType, ZwaveValue | None] = {}
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
            check_all_endpoints=True,
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
            THERMOSTAT_HUMIDITY_PROPERTY,
            command_class=CommandClass.SENSOR_MULTILEVEL,
            add_to_watched_value_ids=True,
            check_all_endpoints=True,
        )
        self._fan_mode = self.get_zwave_value(
            THERMOSTAT_MODE_PROPERTY,
            CommandClass.THERMOSTAT_FAN_MODE,
            add_to_watched_value_ids=True,
            check_all_endpoints=True,
        )
        self._fan_state = self.get_zwave_value(
            THERMOSTAT_OPERATING_STATE_PROPERTY,
            CommandClass.THERMOSTAT_FAN_STATE,
            add_to_watched_value_ids=True,
            check_all_endpoints=True,
        )
        self._set_modes_and_presets()
        if self._current_mode and len(self._hvac_presets) > 1:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        # If any setpoint value exists, we can assume temperature
        # can be set
        if any(self._setpoint_values.values()):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if HVACMode.HEAT_COOL in self.hvac_modes:
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
        if self._fan_mode:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

    def _setpoint_value_or_raise(
        self, setpoint_type: ThermostatSetpointType
    ) -> ZwaveValue:
        """Return a ZwaveValue for a setpoint or raise if not available."""
        if (val := self._setpoint_values[setpoint_type]) is None:
            raise ValueError("Value requested is not available")

        return val

    def _setpoint_temperature(
        self, setpoint_type: ThermostatSetpointType
    ) -> float | None:
        """Optionally return the temperature value of a setpoint."""
        try:
            temp = self._setpoint_value_or_raise(setpoint_type)
        except (IndexError, ValueError):
            return None
        return get_value_of_zwave_value(temp)

    def _set_modes_and_presets(self) -> None:
        """Convert Z-Wave Thermostat modes into Home Assistant modes and presets."""
        all_modes: dict[HVACMode, int | None] = {}
        all_presets: dict[str, int | None] = {PRESET_NONE: None}

        # Z-Wave uses one list for both modes and presets.
        # Iterate over all Z-Wave ThermostatModes
        # and extract the hvac modes and presets.
        if self._current_mode is None:
            self._hvac_modes = {
                ZW_HVAC_MODE_MAP[ThermostatMode.HEAT]: ThermostatMode.HEAT
            }
            return
        for mode_id, mode_name in self._current_mode.metadata.states.items():
            mode_id = int(mode_id)
            if mode_id in THERMOSTAT_MODES:
                # treat value as hvac mode
                if hass_mode := ZW_HVAC_MODE_MAP.get(mode_id):
                    all_modes[hass_mode] = mode_id
                # Dry and Fan modes are in the process of being migrated from
                # presets to hvac modes. In the meantime, we will set them as
                # both, presets and hvac modes, to maintain backwards compatibility
                if mode_id in (ThermostatMode.DRY, ThermostatMode.FAN):
                    all_presets[mode_name] = mode_id
            else:
                # treat value as hvac preset
                all_presets[mode_name] = mode_id

        self._hvac_modes = all_modes
        self._hvac_presets = all_presets

    @property
    def _current_mode_setpoint_enums(self) -> list[ThermostatSetpointType]:
        """Return the list of enums that are relevant to the current thermostat mode."""
        if self._current_mode is None or self._current_mode.value is None:
            # Thermostat(valve) with no support for setting a mode
            # is considered heating-only
            return [ThermostatSetpointType.HEATING]
        return THERMOSTAT_MODE_SETPOINT_MAP.get(int(self._current_mode.value), [])

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        if (
            self._unit_value
            and self._unit_value.metadata.unit
            and "f" in self._unit_value.metadata.unit.lower()
        ):
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self._current_mode is None:
            # Thermostat(valve) with no support for setting
            # a mode is considered heating-only
            return HVACMode.HEAT
        if self._current_mode.value is None:
            # guard missing value
            return HVACMode.HEAT
        return ZW_HVAC_MODE_MAP.get(int(self._current_mode.value), HVACMode.HEAT_COOL)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return list(self._hvac_modes)

    @property
    def hvac_action(self) -> HVACAction | None:
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
        return get_value_of_zwave_value(self._current_humidity)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return get_value_of_zwave_value(self._current_temp)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if (
            self._current_mode and self._current_mode.value is None
        ) or not self._current_mode_setpoint_enums:
            # guard missing value
            return None
        if len(self._current_mode_setpoint_enums) > 1:
            # current mode has a temperature range
            return None

        return self._setpoint_temperature(self._current_mode_setpoint_enums[0])

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        if (
            self._current_mode and self._current_mode.value is None
        ) or not self._current_mode_setpoint_enums:
            # guard missing value
            return None
        if len(self._current_mode_setpoint_enums) < 2:
            # current mode has a single temperature
            return None

        return self._setpoint_temperature(self._current_mode_setpoint_enums[1])

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        if (
            self._current_mode and self._current_mode.value is None
        ) or not self._current_mode_setpoint_enums:
            # guard missing value
            return None
        if len(self._current_mode_setpoint_enums) < 2:
            # current mode has a single temperature
            return None

        return self._setpoint_temperature(self._current_mode_setpoint_enums[0])

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._current_mode is None or self._current_mode.value is None:
            # guard missing value
            return None
        if int(self._current_mode.value) not in THERMOSTAT_MODES:
            return_val: str = cast(
                str,
                self._current_mode.metadata.states.get(str(self._current_mode.value)),
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
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        min_temp = DEFAULT_MIN_TEMP
        base_unit: str = UnitOfTemperature.CELSIUS
        try:
            temp = self._setpoint_value_or_raise(self._current_mode_setpoint_enums[0])
            if temp.metadata.min:
                min_temp = temp.metadata.min
                base_unit = self.temperature_unit
        # In case of any error, we fallback to the default
        except (IndexError, ValueError, TypeError):
            pass

        return TemperatureConverter.convert(min_temp, base_unit, self.temperature_unit)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        max_temp = DEFAULT_MAX_TEMP
        base_unit: str = UnitOfTemperature.CELSIUS
        try:
            temp = self._setpoint_value_or_raise(self._current_mode_setpoint_enums[0])
            if temp.metadata.max:
                max_temp = temp.metadata.max
                base_unit = self.temperature_unit
        # In case of any error, we fallback to the default
        except (IndexError, ValueError, TypeError):
            pass

        return TemperatureConverter.convert(max_temp, base_unit, self.temperature_unit)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        assert self._fan_mode is not None
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

        await self._async_set_value(self._fan_mode, new_state)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)

        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if len(self._current_mode_setpoint_enums) == 1:
            setpoint: ZwaveValue = self._setpoint_value_or_raise(
                self._current_mode_setpoint_enums[0]
            )
            target_temp: float | None = kwargs.get(ATTR_TEMPERATURE)
            if target_temp is not None:
                await self._async_set_value(setpoint, target_temp)
        elif len(self._current_mode_setpoint_enums) == 2:
            setpoint_low: ZwaveValue = self._setpoint_value_or_raise(
                self._current_mode_setpoint_enums[0]
            )
            setpoint_high: ZwaveValue = self._setpoint_value_or_raise(
                self._current_mode_setpoint_enums[1]
            )
            target_temp_low: float | None = kwargs.get(ATTR_TARGET_TEMP_LOW)
            target_temp_high: float | None = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if target_temp_low is not None:
                await self._async_set_value(setpoint_low, target_temp_low)
            if target_temp_high is not None:
                await self._async_set_value(setpoint_high, target_temp_high)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if (hvac_mode_id := self._hvac_modes.get(hvac_mode)) is None:
            raise ValueError(f"Received an invalid hvac mode: {hvac_mode}")

        if not self._current_mode:
            # Thermostat(valve) has no support for setting a mode, so we make it a no-op
            return

        await self._async_set_value(self._current_mode, hvac_mode_id)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        assert self._current_mode is not None
        if preset_mode == PRESET_NONE:
            # try to restore to the (translated) main hvac mode
            await self.async_set_hvac_mode(self.hvac_mode)
            return
        preset_mode_value = self._hvac_presets.get(preset_mode)
        if preset_mode_value is None:
            raise ValueError(f"Received an invalid preset mode: {preset_mode}")
        # Dry and Fan preset modes are deprecated as of Home Assistant 2023.8.
        # Please use Dry and Fan HVAC modes instead.
        if preset_mode_value in (ThermostatMode.DRY, ThermostatMode.FAN):
            LOGGER.warning(
                "Dry and Fan preset modes are deprecated and will be removed in Home "
                "Assistant 2024.2. Please use the corresponding Dry and Fan HVAC "
                "modes instead"
            )
            async_create_issue(
                self.hass,
                DOMAIN,
                f"dry_fan_presets_deprecation_{self.entity_id}",
                breaks_in_ha_version="2024.2.0",
                is_fixable=True,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="dry_fan_presets_deprecation",
                translation_placeholders={
                    "entity_id": self.entity_id,
                },
            )

        await self._async_set_value(self._current_mode, preset_mode_value)


class DynamicCurrentTempClimate(ZWaveClimate):
    """Representation of a thermostat that can dynamically use a different Zwave Value for current temp."""

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize thermostat."""
        super().__init__(config_entry, driver, info)
        self.data_template = cast(
            DynamicCurrentTempClimateDataTemplate, self.info.platform_data_template
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        assert self.info.platform_data
        val = get_value_of_zwave_value(
            self.data_template.current_temperature_value(self.info.platform_data)
        )
        return val if val is not None else super().current_temperature
