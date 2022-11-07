"""Support for HitachiAirToAirHeatPump."""
from __future__ import annotations

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState, Protocol
from pyoverkiz.types import StateType as OverkizStateType

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
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_HOLIDAY_MODE = "holiday_mode"

FAN_SPEED_STATE = {
    Protocol.OVP: OverkizState.OVP_FAN_SPEED,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_FAN_SPEED,
}

LEAVE_HOME_STATE = {
    Protocol.OVP: OverkizState.OVP_LEAVE_HOME,
    Protocol.HLRR_WIFI: OverkizState.HLRRWIFI_LEAVE_HOME,
}

MAIN_OPERATION_STATE = [
    OverkizState.OVP_MAIN_OPERATION,
    OverkizState.HLRRWIFI_MAIN_OPERATION,
]
MODE_CHANGE_STATE = [OverkizState.OVP_MODE_CHANGE, OverkizState.HLRRWIFI_MODE_CHANGE]
ROOM_TEMPERATURE_STATE = [
    OverkizState.OVP_ROOM_TEMPERATURE,
    OverkizState.HLRRWIFI_ROOM_TEMPERATURE,
]
SWING_STATE = [OverkizState.OVP_SWING, OverkizState.HLRRWIFI_SWING]

OVERKIZ_TO_HVAC_MODES: dict[str, str] = {
    OverkizCommandParam.AUTOHEATING: HVACMode.AUTO,
    OverkizCommandParam.AUTOCOOLING: HVACMode.AUTO,
    OverkizCommandParam.OFF: HVACMode.OFF,
    OverkizCommandParam.HEATING: HVACMode.HEAT,
    OverkizCommandParam.FAN: HVACMode.FAN_ONLY,
    OverkizCommandParam.DEHUMIDIFY: HVACMode.DRY,
    OverkizCommandParam.COOLING: HVACMode.COOL,
    OverkizCommandParam.AUTO: HVACMode.AUTO,
}

HVAC_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODES.items()}

OVERKIZ_TO_SWING_MODES: dict[str, str] = {
    OverkizCommandParam.BOTH: SWING_BOTH,
    OverkizCommandParam.HORIZONTAL: SWING_HORIZONTAL,
    OverkizCommandParam.STOP: SWING_OFF,
    OverkizCommandParam.VERTICAL: SWING_VERTICAL,
}

SWING_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_SWING_MODES.items()}

OVERKIZ_TO_FAN_MODES: dict[Protocol, dict[str, str]] = {
    Protocol.OVP: {
        OverkizCommandParam.AUTO: FAN_AUTO,
        OverkizCommandParam.HI: FAN_HIGH,
        OverkizCommandParam.LO: FAN_LOW,
        OverkizCommandParam.MED: FAN_MEDIUM,
        OverkizCommandParam.SILENT: "silent",
    },
    Protocol.HLRR_WIFI: {
        OverkizCommandParam.AUTO: FAN_AUTO,
        OverkizCommandParam.HIGH: FAN_HIGH,
        OverkizCommandParam.LOW: FAN_LOW,
        OverkizCommandParam.MEDIUM: FAN_MEDIUM,
        OverkizCommandParam.SILENT: "silent",
    },
}

# TODO figure out if we can reverse the dictionary above
# FAN_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_FAN_MODES.items()}

FAN_MODES_TO_OVERKIZ: dict[Protocol, dict[str, str]] = {
    Protocol.OVP: {
        FAN_AUTO: OverkizCommandParam.AUTO,
        FAN_HIGH: OverkizCommandParam.HI,
        FAN_LOW: OverkizCommandParam.LO,
        FAN_MEDIUM: OverkizCommandParam.MED,
        "silent": OverkizCommandParam.SILENT,
    },
    Protocol.HLRR_WIFI: {
        FAN_AUTO: OverkizCommandParam.AUTO,
        FAN_HIGH: OverkizCommandParam.HIGH,
        FAN_LOW: OverkizCommandParam.LOW,
        FAN_MEDIUM: OverkizCommandParam.MEDIUM,
        "silent": OverkizCommandParam.SILENT,
    },
}


class HitachiAirToAirHeatPump(OverkizEntity, ClimateEntity):
    """Representation of Hitachi Air To Air HeatPump."""

    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ]
    _attr_preset_modes = [PRESET_NONE, PRESET_HOLIDAY_MODE]
    _attr_swing_modes = [*SWING_MODES_TO_OVERKIZ]
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = TEMP_CELSIUS

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

        if self.executor.has_state(*SWING_STATE):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        if self._attr_device_info:
            self._attr_device_info["manufacturer"] = "Hitachi"

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        if self._select_state(*MAIN_OPERATION_STATE) == OverkizCommandParam.OFF:
            return HVACMode.OFF

        return OVERKIZ_TO_HVAC_MODES[self._select_state(*MODE_CHANGE_STATE)]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
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

        states = self.device.states
        if (
            state := states[FAN_SPEED_STATE[self.device.protocol]]
        ) and state.value_as_str:
            return OVERKIZ_TO_FAN_MODES[self.device.protocol][state.value_as_str]

        return None

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return [*FAN_MODES_TO_OVERKIZ[self.device.protocol]]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._global_control(
            fan_mode=FAN_MODES_TO_OVERKIZ[self.device.protocol][fan_mode]
        )

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return OVERKIZ_TO_SWING_MODES[self._select_state(*SWING_STATE)]

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self._global_control(swing_mode=SWING_MODES_TO_OVERKIZ[swing_mode])

    @property
    def target_temperature(self) -> float:
        """Return the temperature."""
        return self._select_state(OverkizState.CORE_TARGET_TEMPERATURE)

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        return self._select_state(*ROOM_TEMPERATURE_STATE)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._global_control(target_temperature=int(temperature))

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        leave_home_state = self._select_state(*LEAVE_HOME_STATE)

        if leave_home_state == OverkizCommandParam.ON:
            return PRESET_HOLIDAY_MODE

        if leave_home_state == OverkizCommandParam.OFF:
            return PRESET_NONE

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_HOLIDAY_MODE:
            await self._global_control(leave_home=OverkizCommandParam.ON)

        if preset_mode == PRESET_NONE:
            await self._global_control(leave_home=OverkizCommandParam.OFF)

    async def _global_control(
        self,
        main_operation: str = None,
        target_temperature: float = None,
        fan_mode: str = None,
        hvac_mode: str = None,
        swing_mode: str = None,
        leave_home: str = None,
    ) -> None:
        """Execute globalControl command with all parameters."""
        if self.device.protocol == Protocol.OVP:
            await self.executor.async_execute_command(
                OverkizCommand.GLOBAL_CONTROL,
                main_operation
                or self._select_state(*MAIN_OPERATION_STATE),  # Main Operation
                target_temperature
                or self._select_state(
                    OverkizState.CORE_TARGET_TEMPERATURE
                ),  # Target Temperature
                fan_mode or self._select_state(*FAN_SPEED_STATE),  # Fan Mode
                hvac_mode or self._select_state(*MODE_CHANGE_STATE),  # Mode
                swing_mode or self._select_state(*SWING_STATE),  # Swing Mode
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.GLOBAL_CONTROL,
                main_operation
                or self._select_state(*MAIN_OPERATION_STATE),  # Main Operation
                target_temperature
                or self._select_state(
                    OverkizState.CORE_TARGET_TEMPERATURE
                ),  # Target Temperature
                fan_mode or self._select_state(*FAN_SPEED_STATE),  # Fan Mode
                hvac_mode or self._select_state(*MODE_CHANGE_STATE),  # Mode
                swing_mode or self._select_state(*SWING_STATE),  # Swing Mode
                leave_home or self._select_state(*LEAVE_HOME_STATE),  # Leave Home
            )

    def _select_state(self, *states: str) -> OverkizStateType:
        """Make all strings lowercase, since Hi Kumo server returns capitalized strings for some devices."""
        state = self.executor.select_state(*states)

        if state and isinstance(state, str):
            return state.lower()

        return state
