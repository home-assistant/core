"""Support for HitachiAirToAirHeatPump."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState, Protocol

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

FAN_SPEED_STATE = {
    Protocol.OVP: OverkizState.OVP_FAN_SPEED,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_FAN_SPEED,
}

LEAVE_HOME_STATE = {
    Protocol.OVP: OverkizState.OVP_LEAVE_HOME,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_LEAVE_HOME,
}

MAIN_OPERATION_STATE = {
    Protocol.OVP: OverkizState.OVP_MAIN_OPERATION,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_MAIN_OPERATION,
}

MODE_CHANGE_STATE = {
    Protocol.OVP: OverkizState.OVP_MODE_CHANGE,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_MODE_CHANGE,
}

ROOM_TEMPERATURE_STATE = {
    Protocol.OVP: OverkizState.OVP_ROOM_TEMPERATURE,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_ROOM_TEMPERATURE,
}

SWING_STATE = {
    Protocol.OVP: OverkizState.OVP_SWING,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_SWING,
}

OVERKIZ_TO_HVAC_MODES: dict[Protocol, dict[str, HVACMode]] = {
    Protocol.OVP: {
        OverkizCommandParam.AUTO_HEATING: HVACMode.AUTO,
        OverkizCommandParam.AUTO_COOLING: HVACMode.AUTO,
        OverkizCommandParam.ON: HVACMode.HEAT,
        OverkizCommandParam.OFF: HVACMode.OFF,
        OverkizCommandParam.HEATING: HVACMode.HEAT,
        OverkizCommandParam.FAN: HVACMode.FAN_ONLY,
        OverkizCommandParam.DEHUMIDIFY: HVACMode.DRY,
        OverkizCommandParam.COOLING: HVACMode.COOL,
    },
    Protocol.HLRR_WIFI: {
        OverkizCommandParam.AUTOHEATING: HVACMode.AUTO,
        OverkizCommandParam.AUTOCOOLING: HVACMode.AUTO,
        OverkizCommandParam.ON: HVACMode.HEAT,
        OverkizCommandParam.OFF: HVACMode.OFF,
        OverkizCommandParam.HEATING: HVACMode.HEAT,
        OverkizCommandParam.FAN: HVACMode.FAN_ONLY,
        OverkizCommandParam.DEHUMIDIFY: HVACMode.DRY,
        OverkizCommandParam.COOLING: HVACMode.COOL,
        OverkizCommandParam.AUTO: HVACMode.AUTO,
    },
}

HVAC_MODES_TO_OVERKIZ: dict[Protocol, dict[HVACMode, str]] = {
    Protocol.OVP: {
        HVACMode.AUTO: OverkizCommandParam.AUTO_COOLING,
        HVACMode.HEAT: OverkizCommandParam.HEATING,
        HVACMode.OFF: OverkizCommandParam.HEATING,
        HVACMode.FAN_ONLY: OverkizCommandParam.FAN,
        HVACMode.DRY: OverkizCommandParam.DEHUMIDIFY,
        HVACMode.COOL: OverkizCommandParam.COOLING,
    },
    Protocol.HLRR_WIFI: {
        HVACMode.AUTO: OverkizCommandParam.AUTO,
        HVACMode.HEAT: OverkizCommandParam.HEATING,
        HVACMode.OFF: OverkizCommandParam.AUTO,
        HVACMode.FAN_ONLY: OverkizCommandParam.FAN,
        HVACMode.DRY: OverkizCommandParam.DEHUMIDIFY,
        HVACMode.COOL: OverkizCommandParam.COOLING,
    },
}

OVERKIZ_TO_SWING_MODES: dict[str, str] = {
    OverkizCommandParam.BOTH: SWING_BOTH,
    OverkizCommandParam.HORIZONTAL: SWING_HORIZONTAL,
    OverkizCommandParam.STOP: SWING_OFF,
    OverkizCommandParam.VERTICAL: SWING_VERTICAL,
}

SWING_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_SWING_MODES.items()}

# Fan modes differ between OVP and HLRRWIFI protocol
OVERKIZ_TO_FAN_MODES: dict[Protocol, dict[str, str]] = {
    Protocol.OVP: {
        OverkizCommandParam.AUTO: FAN_AUTO,
        OverkizCommandParam.HIGH: FAN_HIGH,  # fallback, state can be exposed as MEDIUM, new state = med
        OverkizCommandParam.HI: FAN_HIGH,
        OverkizCommandParam.LOW: FAN_LOW,
        OverkizCommandParam.LO: FAN_LOW,
        OverkizCommandParam.MEDIUM: FAN_MEDIUM,  # fallback, state can be exposed as MEDIUM, new state = med
        OverkizCommandParam.MED: FAN_MEDIUM,
        OverkizCommandParam.SILENT: FAN_SILENT,
    },
    Protocol.HLRR_WIFI: {
        OverkizCommandParam.AUTO: FAN_AUTO,
        OverkizCommandParam.HIGH: FAN_HIGH,
        OverkizCommandParam.LOW: FAN_LOW,
        OverkizCommandParam.MEDIUM: FAN_MEDIUM,
        OverkizCommandParam.SILENT: FAN_SILENT,
    },
}

FAN_MODES_TO_OVERKIZ: dict[Protocol, dict[str, str]] = {
    Protocol.OVP: {
        FAN_AUTO: OverkizCommandParam.AUTO,
        FAN_HIGH: OverkizCommandParam.HI,
        FAN_LOW: OverkizCommandParam.LO,
        FAN_MEDIUM: OverkizCommandParam.MED,
        FAN_SILENT: OverkizCommandParam.SILENT,
    },
    Protocol.HLRR_WIFI: {
        FAN_AUTO: OverkizCommandParam.AUTO,
        FAN_HIGH: OverkizCommandParam.HIGH,
        FAN_LOW: OverkizCommandParam.LOW,
        FAN_MEDIUM: OverkizCommandParam.MEDIUM,
        FAN_SILENT: OverkizCommandParam.SILENT,
    },
}

# This device is more complex since there is an OVP and an HLLRWIFI version, with different state mappings.
# We need to make all state strings lowercase, since Hi Kumo server returns capitalized strings for some states. (without a clear pattern)


class HitachiAirToAirHeatPump(OverkizEntity, ClimateEntity):
    """Representation of Hitachi Air To Air HeatPump."""

    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ[Protocol.OVP]]
    _attr_preset_modes = [PRESET_NONE, PRESET_HOLIDAY_MODE]
    _attr_swing_modes = [*SWING_MODES_TO_OVERKIZ]
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
        )

        self.protocol = cast(Protocol, self.device.protocol)

        if self.device.states.get(SWING_STATE[self.protocol]):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        if self._attr_device_info:
            self._attr_device_info["manufacturer"] = "Hitachi"

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if (
            main_op_state := self.device.states[MAIN_OPERATION_STATE[self.protocol]]
        ) and main_op_state.value_as_str:
            if main_op_state.value_as_str.lower() == OverkizCommandParam.OFF:
                return HVACMode.OFF

        if (
            mode_change_state := self.device.states[MODE_CHANGE_STATE[self.protocol]]
        ) and mode_change_state.value_as_str:
            return OVERKIZ_TO_HVAC_MODES[self.protocol][mode_change_state.value_as_str]

        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._global_control(main_operation=OverkizCommandParam.OFF)
        else:
            await self._global_control(
                main_operation=OverkizCommandParam.ON,
                hvac_mode=HVAC_MODES_TO_OVERKIZ[self.protocol][hvac_mode],
            )

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if (
            state := self.device.states[FAN_SPEED_STATE[self.protocol]]
        ) and state.value_as_str:
            return OVERKIZ_TO_FAN_MODES[self.protocol][state.value_as_str]

        return None

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return [*FAN_MODES_TO_OVERKIZ[self.protocol]]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._global_control(
            fan_mode=FAN_MODES_TO_OVERKIZ[self.protocol][fan_mode]
        )

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        if (
            state := self.device.states[SWING_STATE[self.protocol]]
        ) and state.value_as_str:
            return OVERKIZ_TO_SWING_MODES[state.value_as_str]

        return None

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self._global_control(swing_mode=SWING_MODES_TO_OVERKIZ[swing_mode])

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature."""
        if (
            temperature := self.device.states[OverkizState.CORE_TARGET_TEMPERATURE]
        ) and temperature.value_as_int:
            return temperature.value_as_int

        return None

    @property
    def current_temperature(self) -> int | None:
        """Return current temperature."""
        if (
            state := self.device.states[ROOM_TEMPERATURE_STATE[self.protocol]]
        ) and state.value_as_int:
            return state.value_as_int

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = cast(float, kwargs.get(ATTR_TEMPERATURE))
        await self._global_control(target_temperature=int(temperature))

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            self.protocol == Protocol.OVP
            and (state := self.device.states[OverkizState.CORE_HOLIDAYS_MODE_STATE])
            and state.value_as_str
        ):
            if state.value_as_str == OverkizCommandParam.ON:
                return PRESET_HOLIDAY_MODE

            if state.value_as_str == OverkizCommandParam.OFF:
                return PRESET_NONE

        if (
            self.protocol == Protocol.HLRR_WIFI
            and (state := self.device.states[LEAVE_HOME_STATE[self.protocol]])
            and state.value_as_str
        ):
            if state.value_as_str == OverkizCommandParam.ON:
                return PRESET_HOLIDAY_MODE

            if state.value_as_str == OverkizCommandParam.OFF:
                return PRESET_NONE

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # OVP uses setHolidays, where HLRRWIFI uses an extra parameter in global control
        if self.protocol == Protocol.HLRR_WIFI:
            if preset_mode == PRESET_HOLIDAY_MODE:
                await self._global_control(leave_home=OverkizCommandParam.ON)

            if preset_mode == PRESET_NONE:
                await self._global_control(leave_home=OverkizCommandParam.OFF)

        if self.protocol == Protocol.OVP:
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

    def _control_backfill(
        self, value: str | None, state_name: str, fallback_value: str
    ) -> str:
        """Overkiz doesn't accept commands with undefined parameters. This function is guaranteed to return a `str` which is the provided `value` if set, or the current device state if set, or the provided `fallback_value` otherwise."""
        if value:
            return value
        state = self.device.states[state_name]
        if state and state.value_as_str:
            return state.value_as_str
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
        """Execute globalControl command with all parameters. There is no option to only set a single parameter, without passing all other values."""

        main_operation = main_operation or OverkizCommandParam.ON
        target_temperature = target_temperature or self.target_temperature
        fan_mode = self._control_backfill(
            fan_mode,
            FAN_SPEED_STATE[self.protocol],
            OverkizCommandParam.AUTO,
        )
        hvac_mode = self._control_backfill(
            hvac_mode,
            MODE_CHANGE_STATE[self.protocol],
            OverkizCommandParam.AUTO,
        )
        swing_mode = self._control_backfill(
            swing_mode,
            SWING_STATE[self.protocol],
            OverkizCommandParam.STOP,
        )

        if self.protocol == Protocol.OVP:
            # OVP protocol has specific fan_mode values; they require cleaning in case protocol HLLR_WIFI values are leaking
            if fan_mode == OverkizCommandParam.MEDIUM:
                fan_mode = OverkizCommandParam.MED
            elif fan_mode == OverkizCommandParam.HIGH:
                fan_mode = OverkizCommandParam.HI
            elif fan_mode == OverkizCommandParam.LOW:
                fan_mode = OverkizCommandParam.LO
        elif hvac_mode in [
            OverkizCommandParam.AUTOCOOLING,
            OverkizCommandParam.AUTOHEATING,
        ]:
            # HLLRWIFI protocol has `autoCooling` and `autoHeating` as valid states, but they cannot be used as commands and need to be converted into `auto`
            hvac_mode = OverkizCommandParam.AUTO

        command_data = [
            main_operation,  # Main Operation
            target_temperature,  # Target Temperature
            fan_mode,  # Fan Mode
            hvac_mode,  # Mode
            swing_mode,  # Swing Mode
        ]

        if self.protocol == Protocol.HLRR_WIFI:
            # HLLR_WIFI protocol requires the additional leave_mode parameter
            leave_home = self._control_backfill(
                leave_home,
                LEAVE_HOME_STATE[self.protocol],
                OverkizCommandParam.OFF,
            )
            command_data.append(leave_home)

        await self.executor.async_execute_command(
            OverkizCommand.GLOBAL_CONTROL, *command_data
        )
