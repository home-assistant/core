"""Support for ESPHome climate devices."""
from __future__ import annotations

from aioesphomeapi import (
    ClimateAction,
    ClimateFanMode,
    ClimateInfo,
    ClimateMode,
    ClimateState,
    ClimateSwingMode,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)

from . import (
    EsphomeEntity,
    esphome_map_enum,
    esphome_state_property,
    platform_async_setup_entry,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up ESPHome climate devices based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="climate",
        info_type=ClimateInfo,
        entity_type=EsphomeClimateEntity,
        state_type=ClimateState,
    )


@esphome_map_enum
def _climate_modes():
    return {
        ClimateMode.OFF: HVAC_MODE_OFF,
        ClimateMode.AUTO: HVAC_MODE_HEAT_COOL,
        ClimateMode.COOL: HVAC_MODE_COOL,
        ClimateMode.HEAT: HVAC_MODE_HEAT,
        ClimateMode.FAN_ONLY: HVAC_MODE_FAN_ONLY,
        ClimateMode.DRY: HVAC_MODE_DRY,
    }


@esphome_map_enum
def _climate_actions():
    return {
        ClimateAction.OFF: CURRENT_HVAC_OFF,
        ClimateAction.COOLING: CURRENT_HVAC_COOL,
        ClimateAction.HEATING: CURRENT_HVAC_HEAT,
        ClimateAction.IDLE: CURRENT_HVAC_IDLE,
        ClimateAction.DRYING: CURRENT_HVAC_DRY,
        ClimateAction.FAN: CURRENT_HVAC_FAN,
    }


@esphome_map_enum
def _fan_modes():
    return {
        ClimateFanMode.ON: FAN_ON,
        ClimateFanMode.OFF: FAN_OFF,
        ClimateFanMode.AUTO: FAN_AUTO,
        ClimateFanMode.LOW: FAN_LOW,
        ClimateFanMode.MEDIUM: FAN_MEDIUM,
        ClimateFanMode.HIGH: FAN_HIGH,
        ClimateFanMode.MIDDLE: FAN_MIDDLE,
        ClimateFanMode.FOCUS: FAN_FOCUS,
        ClimateFanMode.DIFFUSE: FAN_DIFFUSE,
    }


@esphome_map_enum
def _swing_modes():
    return {
        ClimateSwingMode.OFF: SWING_OFF,
        ClimateSwingMode.BOTH: SWING_BOTH,
        ClimateSwingMode.VERTICAL: SWING_VERTICAL,
        ClimateSwingMode.HORIZONTAL: SWING_HORIZONTAL,
    }


class EsphomeClimateEntity(EsphomeEntity, ClimateEntity):
    """A climate implementation for ESPHome."""

    @property
    def _static_info(self) -> ClimateInfo:
        return super()._static_info

    @property
    def _state(self) -> ClimateState | None:
        return super()._state

    @property
    def precision(self) -> float:
        """Return the precision of the climate device."""
        precicions = [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        for prec in precicions:
            if self._static_info.visual_temperature_step >= prec:
                return prec
        # Fall back to highest precision, tenths
        return PRECISION_TENTHS

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available operation modes."""
        return [
            _climate_modes.from_esphome(mode)
            for mode in self._static_info.supported_modes
        ]

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [
            _fan_modes.from_esphome(mode)
            for mode in self._static_info.supported_fan_modes
        ]

    @property
    def preset_modes(self):
        """Return preset modes."""
        return [PRESET_AWAY, PRESET_HOME] if self._static_info.supports_away else []

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        return [
            _swing_modes.from_esphome(mode)
            for mode in self._static_info.supported_swing_modes
        ]

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        # Round to one digit because of floating point math
        return round(self._static_info.visual_temperature_step, 1)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._static_info.visual_min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._static_info.visual_max_temperature

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        features = 0
        if self._static_info.supports_two_point_target_temperature:
            features |= SUPPORT_TARGET_TEMPERATURE_RANGE
        else:
            features |= SUPPORT_TARGET_TEMPERATURE
        if self._static_info.supports_away:
            features |= SUPPORT_PRESET_MODE
        if self._static_info.supported_fan_modes:
            features |= SUPPORT_FAN_MODE
        if self._static_info.supported_swing_modes:
            features |= SUPPORT_SWING_MODE
        return features

    # https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
    # pylint: disable=invalid-overridden-method

    @esphome_state_property
    def hvac_mode(self) -> str | None:
        """Return current operation ie. heat, cool, idle."""
        return _climate_modes.from_esphome(self._state.mode)

    @esphome_state_property
    def hvac_action(self) -> str | None:
        """Return current action."""
        # HA has no support feature field for hvac_action
        if not self._static_info.supports_action:
            return None
        return _climate_actions.from_esphome(self._state.action)

    @esphome_state_property
    def fan_mode(self):
        """Return current fan setting."""
        return _fan_modes.from_esphome(self._state.fan_mode)

    @esphome_state_property
    def preset_mode(self):
        """Return current preset mode."""
        return PRESET_AWAY if self._state.away else PRESET_HOME

    @esphome_state_property
    def swing_mode(self):
        """Return current swing mode."""
        return _swing_modes.from_esphome(self._state.swing_mode)

    @esphome_state_property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state.current_temperature

    @esphome_state_property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._state.target_temperature

    @esphome_state_property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        return self._state.target_temperature_low

    @esphome_state_property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        return self._state.target_temperature_high

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature (and operation mode if set)."""
        data = {"key": self._static_info.key}
        if ATTR_HVAC_MODE in kwargs:
            data["mode"] = _climate_modes.from_hass(kwargs[ATTR_HVAC_MODE])
        if ATTR_TEMPERATURE in kwargs:
            data["target_temperature"] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs:
            data["target_temperature_low"] = kwargs[ATTR_TARGET_TEMP_LOW]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            data["target_temperature_high"] = kwargs[ATTR_TARGET_TEMP_HIGH]
        await self._client.climate_command(**data)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        await self._client.climate_command(
            key=self._static_info.key, mode=_climate_modes.from_hass(hvac_mode)
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        away = preset_mode == PRESET_AWAY
        await self._client.climate_command(key=self._static_info.key, away=away)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        await self._client.climate_command(
            key=self._static_info.key, fan_mode=_fan_modes.from_hass(fan_mode)
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        await self._client.climate_command(
            key=self._static_info.key, swing_mode=_swing_modes.from_hass(swing_mode)
        )
