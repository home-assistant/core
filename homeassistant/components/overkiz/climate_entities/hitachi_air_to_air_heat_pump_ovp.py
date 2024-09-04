"""Support for HitachiAirToAirHeatPump."""

from __future__ import annotations

from typing import Any

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_NONE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..const import DOMAIN
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_HOLIDAY_MODE = "holiday_mode"
FAN_SILENT = "silent"
TEMP_MIN = 16
TEMP_MAX = 32
TEMP_AUTO_MIN = 22
TEMP_AUTO_MAX = 28
AUTO_PIVOT_TEMPERATURE = 25
AUTO_TEMPERATURE_CHANGE_MIN = TEMP_AUTO_MIN - AUTO_PIVOT_TEMPERATURE
AUTO_TEMPERATURE_CHANGE_MAX = TEMP_AUTO_MAX - AUTO_PIVOT_TEMPERATURE

OVERKIZ_TO_HVAC_MODES: dict[str, HVACMode] = {
    OverkizCommandParam.AUTOHEATING: HVACMode.AUTO,
    OverkizCommandParam.AUTOCOOLING: HVACMode.AUTO,
    OverkizCommandParam.ON: HVACMode.HEAT,
    OverkizCommandParam.OFF: HVACMode.OFF,
    OverkizCommandParam.HEATING: HVACMode.HEAT,
    OverkizCommandParam.FAN: HVACMode.FAN_ONLY,
    OverkizCommandParam.DEHUMIDIFY: HVACMode.DRY,
    OverkizCommandParam.COOLING: HVACMode.COOL,
}

HVAC_MODES_TO_OVERKIZ: dict[HVACMode, str] = {
    HVACMode.AUTO: OverkizCommandParam.AUTO,
    HVACMode.HEAT: OverkizCommandParam.HEATING,
    HVACMode.OFF: OverkizCommandParam.HEATING,
    HVACMode.FAN_ONLY: OverkizCommandParam.FAN,
    HVACMode.DRY: OverkizCommandParam.DEHUMIDIFY,
    HVACMode.COOL: OverkizCommandParam.COOLING,
}

OVERKIZ_TO_SWING_MODES: dict[str, str] = {
    OverkizCommandParam.BOTH: SWING_BOTH,
    OverkizCommandParam.HORIZONTAL: SWING_HORIZONTAL,
    OverkizCommandParam.STOP: SWING_OFF,
    OverkizCommandParam.VERTICAL: SWING_VERTICAL,
}

SWING_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_SWING_MODES.items()}

OVERKIZ_TO_FAN_MODES: dict[str, str] = {
    OverkizCommandParam.AUTO: FAN_AUTO,
    OverkizCommandParam.HIGH: FAN_HIGH,  # fallback, state can be exposed as HIGH, new state = hi
    OverkizCommandParam.HI: FAN_HIGH,
    OverkizCommandParam.LOW: FAN_LOW,
    OverkizCommandParam.LO: FAN_LOW,
    OverkizCommandParam.MEDIUM: FAN_MEDIUM,  # fallback, state can be exposed as MEDIUM, new state = med
    OverkizCommandParam.MED: FAN_MEDIUM,
    OverkizCommandParam.SILENT: OverkizCommandParam.SILENT,
}

FAN_MODES_TO_OVERKIZ: dict[str, str] = {
    FAN_AUTO: OverkizCommandParam.AUTO,
    FAN_HIGH: OverkizCommandParam.HI,
    FAN_LOW: OverkizCommandParam.LO,
    FAN_MEDIUM: OverkizCommandParam.MED,
    FAN_SILENT: OverkizCommandParam.SILENT,
}


class HitachiAirToAirHeatPumpOVP(OverkizEntity, ClimateEntity):
    """Representation of Hitachi Air To Air HeatPump."""

    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ]
    _attr_fan_modes = [*FAN_MODES_TO_OVERKIZ]
    _attr_preset_modes = [PRESET_NONE, PRESET_HOLIDAY_MODE]
    _attr_swing_modes = [*SWING_MODES_TO_OVERKIZ]
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        if self.device.states.get(OverkizState.OVP_SWING):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        if self._attr_device_info:
            self._attr_device_info["manufacturer"] = "Hitachi"

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if (
            main_op_state := self.device.states[OverkizState.OVP_MAIN_OPERATION]
        ) and main_op_state.value_as_str:
            if main_op_state.value_as_str.lower() == OverkizCommandParam.OFF:
                return HVACMode.OFF

        if (
            mode_change_state := self.device.states[OverkizState.OVP_MODE_CHANGE]
        ) and mode_change_state.value_as_str:
            # The OVP protocol has 'auto cooling' and 'auto heating' values
            # that are equivalent to the HLRRWIFI protocol without spaces
            sanitized_value = mode_change_state.value_as_str.replace(" ", "").lower()
            return OVERKIZ_TO_HVAC_MODES[sanitized_value]

        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._global_control(main_operation=OverkizCommandParam.OFF)
        else:
            await self._global_control(
                main_operation=OverkizCommandParam.ON,
                hvac_mode=HVAC_MODES_TO_OVERKIZ[hvac_mode],
            )

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if (
            state := self.device.states[OverkizState.OVP_FAN_SPEED]
        ) and state.value_as_str:
            return OVERKIZ_TO_FAN_MODES[state.value_as_str]

        return None

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._global_control(fan_mode=FAN_MODES_TO_OVERKIZ[fan_mode])

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        if (state := self.device.states[OverkizState.OVP_SWING]) and state.value_as_str:
            return OVERKIZ_TO_SWING_MODES[state.value_as_str]

        return None

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self._global_control(swing_mode=SWING_MODES_TO_OVERKIZ[swing_mode])

    @property
    def target_temperature(self) -> int | None:
        """Return the target temperature."""
        if (
            temperature := self.device.states[OverkizState.CORE_TARGET_TEMPERATURE]
        ) and temperature.value_as_int:
            return temperature.value_as_int

        return None

    @property
    def current_temperature(self) -> int | None:
        """Return current temperature."""
        if (
            state := self.device.states[OverkizState.OVP_ROOM_TEMPERATURE]
        ) and state.value_as_int:
            return state.value_as_int

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        await self._global_control(target_temperature=int(kwargs[ATTR_TEMPERATURE]))

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            state := self.device.states[OverkizState.CORE_HOLIDAYS_MODE]
        ) and state.value_as_str:
            if state.value_as_str == OverkizCommandParam.ON:
                return PRESET_HOLIDAY_MODE

            if state.value_as_str == OverkizCommandParam.OFF:
                return PRESET_NONE

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_HOLIDAY_MODE:
            await self.executor.async_execute_command(
                OverkizCommand.SET_HOLIDAYS,
                OverkizCommandParam.ON,
            )
        if preset_mode == PRESET_NONE:
            await self.executor.async_execute_command(
                OverkizCommand.SET_HOLIDAYS,
                OverkizCommandParam.OFF,
            )

    # OVP has this property to control the unit's timer mode
    @property
    def auto_manu_mode(self) -> str | None:
        """Return auto/manu mode."""
        if (
            state := self.device.states[OverkizState.CORE_AUTO_MANU_MODE]
        ) and state.value_as_str:
            return state.value_as_str
        return None

    # OVP has this property to control the target temperature delta in auto mode
    @property
    def temperature_change(self) -> int | None:
        """Return temperature change state."""
        if (
            state := self.device.states[OverkizState.OVP_TEMPERATURE_CHANGE]
        ) and state.value_as_int:
            return state.value_as_int

        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self.hvac_mode == HVACMode.AUTO:
            return TEMP_AUTO_MIN
        return TEMP_MIN

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self.hvac_mode == HVACMode.AUTO:
            return TEMP_AUTO_MAX
        return TEMP_MAX

    def _control_backfill(
        self, value: str | None, state_name: str, fallback_value: str
    ) -> str:
        """Return a parameter value which will be accepted in a command by Overkiz.

        Overkiz doesn't accept commands with undefined parameters. This function
        is guaranteed to return a `str` which is the provided `value` if set, or
        the current device state if set, or the provided `fallback_value` otherwise.
        """
        if value:
            return value
        if (state := self.device.states[state_name]) is not None and (
            value := state.value_as_str
        ) is not None:
            return value
        return fallback_value

    async def _global_control(
        self,
        main_operation: str | None = None,
        target_temperature: int | None = None,
        fan_mode: str | None = None,
        hvac_mode: str | None = None,
        swing_mode: str | None = None,
        leave_home: str | None = None,
    ) -> None:
        """Execute globalControl command with all parameters.

        There is no option to only set a single parameter, without passing
        all other values.
        """

        main_operation = self._control_backfill(
            main_operation, OverkizState.OVP_MAIN_OPERATION, OverkizCommandParam.ON
        )
        fan_mode = self._control_backfill(
            fan_mode,
            OverkizState.OVP_FAN_SPEED,
            OverkizCommandParam.AUTO,
        )
        # Sanitize fan mode: Overkiz is sometimes providing a state that
        # cannot be used as a command. Convert it to HA space and back to Overkiz
        if fan_mode not in FAN_MODES_TO_OVERKIZ.values():
            fan_mode = FAN_MODES_TO_OVERKIZ[OVERKIZ_TO_FAN_MODES[fan_mode]]

        hvac_mode = self._control_backfill(
            hvac_mode,
            OverkizState.OVP_MODE_CHANGE,
            OverkizCommandParam.AUTO,
        ).lower()  # Overkiz returns uppercase states that are not acceptable commands
        if hvac_mode.replace(" ", "") in [
            # Overkiz returns compound states like 'auto cooling' or 'autoHeating'
            # that are not valid commands and need to be mapped to 'auto'
            OverkizCommandParam.AUTOCOOLING,
            OverkizCommandParam.AUTOHEATING,
        ]:
            hvac_mode = OverkizCommandParam.AUTO

        swing_mode = self._control_backfill(
            swing_mode,
            OverkizState.OVP_SWING,
            OverkizCommandParam.STOP,
        )

        # AUTO_MANU parameter is not controlled by HA and is turned "off" when the device is on Holiday mode
        auto_manu_mode = self._control_backfill(
            None, OverkizState.CORE_AUTO_MANU_MODE, OverkizCommandParam.MANU
        )
        if self.preset_mode == PRESET_HOLIDAY_MODE:
            auto_manu_mode = OverkizCommandParam.OFF

        # In all the hvac modes except AUTO, the temperature command parameter is the target temperature
        temperature_command = None
        target_temperature = target_temperature or self.target_temperature
        if hvac_mode == OverkizCommandParam.AUTO:
            # In hvac mode AUTO, the temperature command parameter is a temperature_change
            # which is the delta between a pivot temperature (25) and the target temperature
            temperature_change = 0

            if target_temperature:
                temperature_change = target_temperature - AUTO_PIVOT_TEMPERATURE
            elif self.temperature_change:
                temperature_change = self.temperature_change

            # Keep temperature_change in the API accepted range
            temperature_change = min(
                max(temperature_change, AUTO_TEMPERATURE_CHANGE_MIN),
                AUTO_TEMPERATURE_CHANGE_MAX,
            )

            temperature_command = temperature_change
        else:
            # In other modes, the temperature command is the target temperature
            temperature_command = target_temperature

        command_data = [
            main_operation,  # Main Operation
            temperature_command,  # Temperature Command
            fan_mode,  # Fan Mode
            hvac_mode,  # Mode
            auto_manu_mode,  # Auto Manu Mode
        ]

        await self.executor.async_execute_command(
            OverkizCommand.GLOBAL_CONTROL, *command_data
        )
