"""Support for Atlantic Pass APC Heating Control."""

from __future__ import annotations

from asyncio import sleep
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS

from ..coordinator import OverkizDataUpdateCoordinator
from ..executor import OverkizExecutor
from .atlantic_pass_apc_heating_zone import AtlanticPassAPCHeatingZone

PRESET_SCHEDULE = "schedule"
PRESET_MANUAL = "manual"

OVERKIZ_MODE_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.MANU: PRESET_MANUAL,
    OverkizCommandParam.INTERNAL_SCHEDULING: PRESET_SCHEDULE,
}

# Maps the HVAC current ZoneControl system operating mode.
OVERKIZ_TO_HVAC_ACTION: dict[str, HVACAction] = {
    OverkizCommandParam.COOLING: HVACAction.COOLING,
    OverkizCommandParam.DRYING: HVACAction.DRYING,
    OverkizCommandParam.HEATING: HVACAction.HEATING,
    # There is no known way to differenciate OFF from Idle.
    OverkizCommandParam.STOP: HVACAction.OFF,
}

# Maps the HVAC ZoneControlZone mode.
HVAC_ACTION_TO_HVAC_MODES: dict[HVACAction, HVACMode] = {
    HVACAction.COOLING: HVACMode.COOL,
    HVACAction.DRYING: HVACMode.DRY,
    HVACAction.HEATING: HVACMode.HEAT,
    HVACAction.OFF: HVACMode.OFF,
}

HVAC_ACTION_TO_OVERKIZ_PROFILE_STATE: dict[HVACAction, OverkizState] = {
    HVACAction.COOLING: OverkizState.IO_PASS_APC_COOLING_PROFILE,
    HVACAction.HEATING: OverkizState.IO_PASS_APC_HEATING_PROFILE,
}

HVAC_ACTION_TO_OVERKIZ_MODE_STATE: dict[HVACAction, OverkizState] = {
    HVACAction.COOLING: OverkizState.IO_PASS_APC_COOLING_MODE,
    HVACAction.HEATING: OverkizState.IO_PASS_APC_HEATING_MODE,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_MODE_TO_PRESET_MODES.items()}

TEMPERATURE_ZONECONTROL_DEVICE_INDEX = 20

SUPPORTED_FEATURES = (
    ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)
SUPPORTED_FEATURES_MANUAL = SUPPORTED_FEATURES | ClimateEntityFeature.TARGET_TEMPERATURE
SUPPORTED_FEATURES_AUTO = (
    SUPPORTED_FEATURES | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
)


# Those device depends on a main probe that choose the operating mode (heating, cooling, ...).
class AtlanticPassAPCZoneControlZone(AtlanticPassAPCHeatingZone):
    """Representation of Atlantic Pass APC Heating And Cooling Zone Control."""

    _attr_target_temperature_step = PRECISION_TENTHS

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        # When using derogated temperature, we fallback to legacy behavior.
        if self.is_using_derogated_temperature_fallback:
            return

        self._attr_min_temp = 0
        self._attr_max_temp = 0

        self._attr_supported_features = SUPPORTED_FEATURES

        # Modes are not configurable, they will follow current HVAC Mode of Zone Control.
        self._attr_hvac_modes = []

        # Those are available and tested presets on Shogun.
        self._attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]

        # Those APC Heating and Cooling probes depends on the zone control device (main probe).
        # Only the base device (#1) can be used to get/set some states.
        # Like to retrieve and set the current operating mode (heating, cooling, drying, off).

        self.zone_control_executor: OverkizExecutor | None = None

        if (
            zone_control_device := self.executor.linked_device(
                TEMPERATURE_ZONECONTROL_DEVICE_INDEX
            )
        ) is not None:
            self.zone_control_executor = OverkizExecutor(
                zone_control_device.device_url,
                coordinator,
            )

    @property
    def is_using_derogated_temperature_fallback(self) -> bool:
        """Check if the device behave like the Pass APC Heating Zone."""

        return self.executor.has_command(
            OverkizCommand.SET_DEROGATED_TARGET_TEMPERATURE
        )

    @property
    def zone_control_hvac_action(self) -> HVACAction:
        """Return hvac operation ie. heat, cool, dry, off mode."""

        if self.zone_control_executor is not None and (
            (
                state := self.zone_control_executor.select_state(
                    OverkizState.IO_PASS_APC_OPERATING_MODE
                )
            )
            is not None
        ):
            return OVERKIZ_TO_HVAC_ACTION[cast(str, state)]

        return HVACAction.OFF

    @property
    def is_zone_control_auto_switch_active(self) -> bool:
        """Check if auto mode is available and active on the ZoneControl."""

        if self.zone_control_executor is not None and (
            (
                state := self.zone_control_executor.select_state(
                    OverkizState.CORE_HEATING_COOLING_AUTO_SWITCH
                )
            )
            is not None
        ):
            return cast(str, state) == OverkizCommandParam.ON

        return False

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""

        # When ZoneControl action is heating/cooling but Zone is stopped, means the zone is idle.
        if (
            hvac_action := self.zone_control_hvac_action
        ) in HVAC_ACTION_TO_OVERKIZ_PROFILE_STATE and cast(
            str,
            self.executor.select_state(
                HVAC_ACTION_TO_OVERKIZ_PROFILE_STATE[hvac_action]
            ),
        ) == OverkizCommandParam.STOP:
            return HVACAction.IDLE

        return hvac_action

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool, dry, off mode."""

        if self.is_using_derogated_temperature_fallback:
            return super().hvac_mode

        zone_control_hvac_mode = HVAC_ACTION_TO_HVAC_MODES[
            zone_control_hvac_action := self.zone_control_hvac_action
        ]

        # Selectable mode is kept in synced with the Zone Control current mode.
        # When auto switching is enabled on Zone Control, we can use the HEAT_COOL mode.
        if self.is_zone_control_auto_switch_active:
            selectable_hvac_mode = HVACMode.HEAT_COOL
        else:
            selectable_hvac_mode = zone_control_hvac_mode

        self.sync_attrs_from_mode(selectable_hvac_mode)

        # Device is Stopped, it means the air flux is flowing but its venting door is closed.
        if (
            cast(
                str,
                self.executor.select_state(
                    OverkizState.CORE_COOLING_ON_OFF
                    if zone_control_hvac_action == HVACAction.COOLING
                    else OverkizState.CORE_HEATING_ON_OFF
                ),
            )
            == OverkizCommandParam.OFF
        ):
            return HVACMode.OFF

        return selectable_hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if self.is_using_derogated_temperature_fallback:
            return await super().async_set_hvac_mode(hvac_mode)

        # They are mainly managed by the Zone Control device
        # However, it make sense to map the OFF Mode to the Overkiz STOP Preset

        if hvac_mode == HVACMode.OFF:
            await self.executor.async_execute_command(
                OverkizCommand.SET_COOLING_ON_OFF,
                OverkizCommandParam.OFF,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_ON_OFF,
                OverkizCommandParam.OFF,
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_COOLING_ON_OFF,
                OverkizCommandParam.ON,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_ON_OFF,
                OverkizCommandParam.ON,
            )

        await self.async_refresh_modes()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., schedule, manual."""

        if self.is_using_derogated_temperature_fallback:
            return super().preset_mode

        mode_state = HVAC_ACTION_TO_OVERKIZ_MODE_STATE[self.zone_control_hvac_action]

        if mode_state is not None and (
            mode := OVERKIZ_MODE_TO_PRESET_MODES[
                cast(str, self.executor.select_state(mode_state))
            ]
            is not None
        ):
            return mode

        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        if self.is_using_derogated_temperature_fallback:
            return await super().async_set_preset_mode(preset_mode)

        mode = PRESET_MODES_TO_OVERKIZ[preset_mode]

        # For consistency, it is better both are synced like on the Thermostat.
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_HEATING_MODE, mode
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_COOLING_MODE, mode
        )

        await self.async_refresh_modes()

    @property
    def target_temperature(self) -> float | None:
        """Return hvac target temperature."""

        if self.is_using_derogated_temperature_fallback:
            return super().target_temperature

        hvac_mode = self.hvac_mode

        if hvac_mode == HVACMode.HEAT_COOL:
            return None

        if hvac_mode == HVACMode.COOL:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_COOLING_TARGET_TEMPERATURE
                ),
            )

        if hvac_mode == HVACMode.HEAT:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_HEATING_TARGET_TEMPERATURE
                ),
            )

        return cast(
            float, self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)
        )

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach (cooling)."""

        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None

        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_COOLING_TARGET_TEMPERATURE),
        )

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach (heating)."""
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None

        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_HEATING_TARGET_TEMPERATURE),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""

        if self.is_using_derogated_temperature_fallback:
            return await super().async_set_temperature(**kwargs)

        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        hvac_mode = self.hvac_mode

        if hvac_mode == HVACMode.HEAT_COOL:
            if target_temp_low is not None:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_HEATING_TARGET_TEMPERATURE,
                    target_temp_low,
                )

            if target_temp_high is not None:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_COOLING_TARGET_TEMPERATURE,
                    target_temp_high,
                )

        elif target_temperature is not None:
            if hvac_mode == HVACMode.HEAT:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_HEATING_TARGET_TEMPERATURE,
                    target_temperature,
                )

            elif hvac_mode == HVACMode.COOL:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_COOLING_TARGET_TEMPERATURE,
                    target_temperature,
                )

        await self.executor.async_execute_command(
            OverkizCommand.SET_DEROGATION_ON_OFF_STATE,
            OverkizCommandParam.OFF,
        )

        await self.async_refresh_modes()

    async def async_refresh_modes(self) -> None:
        """Refresh the device modes to have new states."""

        # The device needs a bit of time to update everything before a refresh.
        await sleep(2)

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_HEATING_MODE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_COOLING_MODE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_COOLING_PROFILE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_TARGET_TEMPERATURE
        )

    def sync_attrs_from_mode(self, hvac_mode: HVACMode) -> None:
        """Synchronise attrs from zone control mode."""

        should_write_state = False

        # Selectable mode is kept in synced with the Zone Control current mode.
        # When auto switching is enabled on Zone Control, we can use the HEAT_COOL mode.
        if hvac_mode == HVACMode.HEAT_COOL:
            supported_features = SUPPORTED_FEATURES_AUTO
        else:
            supported_features = SUPPORTED_FEATURES_MANUAL

        # Only HEAT_COOL mode supports temperature range.
        if self._attr_supported_features != supported_features:
            self._attr_supported_features = supported_features
            should_write_state = True

        # It helps keep it consistent with the Zone Control, within the interface.
        if self._attr_hvac_modes != (hvac_modes := [hvac_mode, HVACMode.OFF]):
            self._attr_hvac_modes = hvac_modes
            should_write_state = True

        min_temp = self.get_min_temp(hvac_mode)
        max_temp = self.get_max_temp(hvac_mode)

        if self._attr_min_temp != min_temp or self._attr_max_temp != max_temp:
            self._attr_min_temp = min_temp
            self._attr_max_temp = max_temp
            should_write_state = True

        if should_write_state is True:
            self.async_write_ha_state()

    def get_min_temp(self, hvac_mode: HVACMode) -> float:
        """Compute the minimum temperature."""

        if hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MINIMUM_HEATING_TARGET_TEMPERATURE
                ),
            )

        if hvac_mode == HVACMode.COOL:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MINIMUM_COOLING_TARGET_TEMPERATURE
                ),
            )

        return self._attr_min_temp

    def get_max_temp(self, hvac_mode: HVACMode) -> float:
        """Compute the maximum temperature."""

        if hvac_mode == HVACMode.HEAT:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MAXIMUM_HEATING_TARGET_TEMPERATURE
                ),
            )

        if hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL):
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MAXIMUM_COOLING_TARGET_TEMPERATURE
                ),
            )

        return self._attr_max_temp
