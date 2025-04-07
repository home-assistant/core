"""Support for Atlantic Pass APC Heating Control."""

from __future__ import annotations

from asyncio import sleep
from typing import Any, cast

from propcache.api import cached_property
from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES

from ..coordinator import OverkizDataUpdateCoordinator
from ..executor import OverkizExecutor
from .atlantic_pass_apc_heating_zone import AtlanticPassAPCHeatingZone

PRESET_SCHEDULE = "schedule"
PRESET_MANUAL = "manual"

OVERKIZ_MODE_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.MANU: PRESET_MANUAL,
    OverkizCommandParam.INTERNAL_SCHEDULING: PRESET_SCHEDULE,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_MODE_TO_PRESET_MODES.items()}

# Maps the HVAC current ZoneControl system operating mode.
OVERKIZ_TO_HVAC_ACTION: dict[str, HVACAction] = {
    OverkizCommandParam.COOLING: HVACAction.COOLING,
    OverkizCommandParam.DRYING: HVACAction.DRYING,
    OverkizCommandParam.HEATING: HVACAction.HEATING,
    # There is no known way to differentiate OFF from Idle.
    OverkizCommandParam.STOP: HVACAction.OFF,
}

HVAC_ACTION_TO_OVERKIZ_PROFILE_STATE: dict[HVACAction, OverkizState] = {
    HVACAction.COOLING: OverkizState.IO_PASS_APC_COOLING_PROFILE,
    HVACAction.HEATING: OverkizState.IO_PASS_APC_HEATING_PROFILE,
}

HVAC_ACTION_TO_OVERKIZ_MODE_STATE: dict[HVACAction, OverkizState] = {
    HVACAction.COOLING: OverkizState.IO_PASS_APC_COOLING_MODE,
    HVACAction.HEATING: OverkizState.IO_PASS_APC_HEATING_MODE,
}

TEMPERATURE_ZONECONTROL_DEVICE_INDEX = 1

SUPPORTED_FEATURES: ClimateEntityFeature = (
    ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)

OVERKIZ_THERMAL_CONFIGURATION_TO_HVAC_MODE: dict[
    OverkizCommandParam, tuple[HVACMode, ClimateEntityFeature]
] = {
    OverkizCommandParam.COOLING: (
        HVACMode.COOL,
        SUPPORTED_FEATURES | ClimateEntityFeature.TARGET_TEMPERATURE,
    ),
    OverkizCommandParam.HEATING: (
        HVACMode.HEAT,
        SUPPORTED_FEATURES | ClimateEntityFeature.TARGET_TEMPERATURE,
    ),
    OverkizCommandParam.HEATING_AND_COOLING: (
        HVACMode.HEAT_COOL,
        SUPPORTED_FEATURES | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
    ),
}


# Those device depends on a main probe that choose the operating mode (heating, cooling, ...).
class AtlanticPassAPCZoneControlZone(AtlanticPassAPCHeatingZone):
    """Representation of Atlantic Pass APC Heating And Cooling Zone Control."""

    _attr_target_temperature_step = PRECISION_HALVES

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        # When using derogated temperature, we fallback to legacy behavior.
        if self.is_using_derogated_temperature_fallback:
            return

        self._attr_hvac_modes = []
        self._attr_supported_features = ClimateEntityFeature(0)

        # Modes depends on device capabilities.
        if (thermal_configuration := self.thermal_configuration) is not None:
            (
                device_hvac_mode,
                climate_entity_feature,
            ) = thermal_configuration
            self._attr_hvac_modes = [device_hvac_mode, HVACMode.OFF]
            self._attr_supported_features = climate_entity_feature

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

    @cached_property
    def thermal_configuration(self) -> tuple[HVACMode, ClimateEntityFeature] | None:
        """Retrieve thermal configuration for this devices."""

        if (
            (
                state_thermal_configuration := cast(
                    OverkizCommandParam | None,
                    self.executor.select_state(OverkizState.CORE_THERMAL_CONFIGURATION),
                )
            )
            is not None
            and state_thermal_configuration
            in OVERKIZ_THERMAL_CONFIGURATION_TO_HVAC_MODE
        ):
            return OVERKIZ_THERMAL_CONFIGURATION_TO_HVAC_MODE[
                state_thermal_configuration
            ]

        return None

    @cached_property
    def device_hvac_mode(self) -> HVACMode | None:
        """ZoneControlZone device has a single possible mode."""

        return (
            None
            if self.thermal_configuration is None
            else self.thermal_configuration[0]
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

        if (device_hvac_mode := self.device_hvac_mode) is None:
            return HVACMode.OFF

        cooling_is_off = cast(
            str,
            self.executor.select_state(OverkizState.CORE_COOLING_ON_OFF),
        ) in (OverkizCommandParam.OFF, None)

        heating_is_off = cast(
            str,
            self.executor.select_state(OverkizState.CORE_HEATING_ON_OFF),
        ) in (OverkizCommandParam.OFF, None)

        # Device is Stopped, it means the air flux is flowing but its venting door is closed.
        if (
            (device_hvac_mode == HVACMode.COOL and cooling_is_off)
            or (device_hvac_mode == HVACMode.HEAT and heating_is_off)
            or (
                device_hvac_mode == HVACMode.HEAT_COOL
                and cooling_is_off
                and heating_is_off
            )
        ):
            return HVACMode.OFF

        return device_hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if self.is_using_derogated_temperature_fallback:
            await super().async_set_hvac_mode(hvac_mode)
            return

        # They are mainly managed by the Zone Control device
        # However, it make sense to map the OFF Mode to the Overkiz STOP Preset

        on_off_target_command_param = (
            OverkizCommandParam.OFF
            if hvac_mode == HVACMode.OFF
            else OverkizCommandParam.ON
        )

        await self.executor.async_execute_command(
            OverkizCommand.SET_COOLING_ON_OFF,
            on_off_target_command_param,
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_HEATING_ON_OFF,
            on_off_target_command_param,
        )

        await self.async_refresh_modes()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., schedule, manual."""

        if self.is_using_derogated_temperature_fallback:
            return super().preset_mode

        if (
            self.zone_control_hvac_action in HVAC_ACTION_TO_OVERKIZ_MODE_STATE
            and (
                mode_state := HVAC_ACTION_TO_OVERKIZ_MODE_STATE[
                    self.zone_control_hvac_action
                ]
            )
            and (
                (
                    mode := OVERKIZ_MODE_TO_PRESET_MODES[
                        cast(str, self.executor.select_state(mode_state))
                    ]
                )
                is not None
            )
        ):
            return mode

        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        if self.is_using_derogated_temperature_fallback:
            await super().async_set_preset_mode(preset_mode)
            return

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

        device_hvac_mode = self.device_hvac_mode

        if device_hvac_mode == HVACMode.HEAT_COOL:
            return None

        if device_hvac_mode == HVACMode.COOL:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_COOLING_TARGET_TEMPERATURE
                ),
            )

        if device_hvac_mode == HVACMode.HEAT:
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

        if self.device_hvac_mode != HVACMode.HEAT_COOL:
            return None

        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_COOLING_TARGET_TEMPERATURE),
        )

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach (heating)."""

        if self.device_hvac_mode != HVACMode.HEAT_COOL:
            return None

        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_HEATING_TARGET_TEMPERATURE),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""

        if self.is_using_derogated_temperature_fallback:
            await super().async_set_temperature(**kwargs)
            return

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
            OverkizCommandParam.ON,
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

    @property
    def min_temp(self) -> float:
        """Return Minimum Temperature for AC of this group."""

        device_hvac_mode = self.device_hvac_mode

        if device_hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MINIMUM_HEATING_TARGET_TEMPERATURE
                ),
            )

        if device_hvac_mode == HVACMode.COOL:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MINIMUM_COOLING_TARGET_TEMPERATURE
                ),
            )

        return super().min_temp

    @property
    def max_temp(self) -> float:
        """Return Max Temperature for AC of this group."""

        device_hvac_mode = self.device_hvac_mode

        if device_hvac_mode == HVACMode.HEAT:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MAXIMUM_HEATING_TARGET_TEMPERATURE
                ),
            )

        if device_hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL):
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_MAXIMUM_COOLING_TARGET_TEMPERATURE
                ),
            )

        return super().max_temp
