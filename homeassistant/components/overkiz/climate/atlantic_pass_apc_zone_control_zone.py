"""Support for Atlantic Pass APC Heating Control."""

from dataclasses import dataclass
from typing import Any, cast, override

from propcache.api import cached_property
from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES
from homeassistant.exceptions import ServiceValidationError

from ..const import DOMAIN
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

REFRESH_MODES_COMMANDS: tuple[OverkizCommand, ...] = (
    OverkizCommand.REFRESH_PASS_APC_HEATING_MODE,
    OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE,
    OverkizCommand.REFRESH_PASS_APC_COOLING_MODE,
    OverkizCommand.REFRESH_PASS_APC_COOLING_PROFILE,
    OverkizCommand.REFRESH_TARGET_TEMPERATURE,
)

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

# Setpoints applied by internal scheduling for each active program profile.
HEATING_PROFILE_TO_TARGET_TEMPERATURE_STATE: dict[str, OverkizState] = {
    OverkizCommandParam.COMFORT: OverkizState.CORE_COMFORT_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.ECO: OverkizState.CORE_ECO_HEATING_TARGET_TEMPERATURE,
}

COOLING_PROFILE_TO_TARGET_TEMPERATURE_STATE: dict[str, OverkizState] = {
    OverkizCommandParam.COMFORT: OverkizState.CORE_COMFORT_COOLING_TARGET_TEMPERATURE,
    OverkizCommandParam.ECO: OverkizState.CORE_ECO_COOLING_TARGET_TEMPERATURE,
}


PROGRAM_SETPOINT_REFRESH_COMMANDS: dict[str, OverkizCommand] = {
    OverkizCommand.SET_ECO_HEATING_TARGET_TEMPERATURE: (
        OverkizCommand.REFRESH_ECO_HEATING_TARGET_TEMPERATURE
    ),
    OverkizCommand.SET_COMFORT_HEATING_TARGET_TEMPERATURE: (
        OverkizCommand.REFRESH_COMFORT_HEATING_TARGET_TEMPERATURE
    ),
    OverkizCommand.SET_ECO_COOLING_TARGET_TEMPERATURE: (
        OverkizCommand.REFRESH_ECO_COOLING_TARGET_TEMPERATURE
    ),
    OverkizCommand.SET_COMFORT_COOLING_TARGET_TEMPERATURE: (
        OverkizCommand.REFRESH_COMFORT_COOLING_TARGET_TEMPERATURE
    ),
}


def _program_refresh_commands(
    commands: list[Command],
) -> tuple[OverkizCommand, ...]:
    """Return the refreshes of the program setpoints written, and the applied one."""

    return (
        *(PROGRAM_SETPOINT_REFRESH_COMMANDS[command.name] for command in commands),
        OverkizCommand.REFRESH_TARGET_TEMPERATURE,
    )


@dataclass(frozen=True, kw_only=True)
class ProgramSetpoints:
    """Eco and comfort setpoints of the time program of one side."""

    mode_state: OverkizState
    low_state: OverkizState
    low_command: OverkizCommand
    high_state: OverkizState
    high_command: OverkizCommand


# While the zone follows its time program, the range shows the eco and comfort
# setpoints of the side running: eco is the lower one when heating, comfort
# the lower one when cooling.
HVAC_MODE_TO_PROGRAM_SETPOINTS: dict[HVACMode, ProgramSetpoints] = {
    HVACMode.HEAT: ProgramSetpoints(
        mode_state=OverkizState.IO_PASS_APC_HEATING_MODE,
        low_state=OverkizState.CORE_ECO_HEATING_TARGET_TEMPERATURE,
        low_command=OverkizCommand.SET_ECO_HEATING_TARGET_TEMPERATURE,
        high_state=OverkizState.CORE_COMFORT_HEATING_TARGET_TEMPERATURE,
        high_command=OverkizCommand.SET_COMFORT_HEATING_TARGET_TEMPERATURE,
    ),
    HVACMode.COOL: ProgramSetpoints(
        mode_state=OverkizState.IO_PASS_APC_COOLING_MODE,
        low_state=OverkizState.CORE_COMFORT_COOLING_TARGET_TEMPERATURE,
        low_command=OverkizCommand.SET_COMFORT_COOLING_TARGET_TEMPERATURE,
        high_state=OverkizState.CORE_ECO_COOLING_TARGET_TEMPERATURE,
        high_command=OverkizCommand.SET_ECO_COOLING_TARGET_TEMPERATURE,
    ),
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

# Heating and cooling zones only expose the setpoints of the side the
# ZoneControl system is running, or ran last while it is stopped or drying.
OVERKIZ_OPERATING_MODE_TO_ACTIVE_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.COOLING: HVACMode.COOL,
    OverkizCommandParam.HEATING: HVACMode.HEAT,
}


# Those device depends on a main probe that choose the
# operating mode (heating, cooling, ...).
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

        # Those APC Heating and Cooling probes depends on the
        # zone control device (main probe). Only the base device
        # (#1) can be used to get/set some states. Like to
        # retrieve and set the current operating mode
        # (heating, cooling, drying, off).

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
                    self.device.states.get_value(
                        OverkizState.CORE_THERMAL_CONFIGURATION
                    ),
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

        return self.device.supports_command(
            OverkizCommand.SET_DEROGATED_TARGET_TEMPERATURE
        )

    @property
    def zone_control_hvac_action(self) -> HVACAction:
        """Return hvac operation ie. heat, cool, dry, off mode."""

        if self.zone_control_executor is not None and (
            (
                state := self.zone_control_executor.device.states.get_value(
                    OverkizState.IO_PASS_APC_OPERATING_MODE
                )
            )
            is not None
        ):
            return OVERKIZ_TO_HVAC_ACTION[cast(str, state)]

        return HVACAction.OFF

    @property
    def active_hvac_mode(self) -> HVACMode | None:
        """Return the device mode, narrowed to the side currently running.

        While the ZoneControl system is stopped or drying, this is the side it
        ran last.
        """

        device_hvac_mode = self.device_hvac_mode

        if (
            device_hvac_mode != HVACMode.HEAT_COOL
            or self.is_using_derogated_temperature_fallback
            or self.zone_control_executor is None
        ):
            return device_hvac_mode

        states = self.zone_control_executor.device.states

        for operating_mode_state in (
            OverkizState.IO_PASS_APC_OPERATING_MODE,
            OverkizState.IO_LAST_PASS_APC_OPERATING_MODE,
        ):
            if (
                active_hvac_mode := OVERKIZ_OPERATING_MODE_TO_ACTIVE_HVAC_MODE.get(
                    cast(str, states.get_value(operating_mode_state))
                )
            ) is not None:
                return active_hvac_mode

        return device_hvac_mode

    @property
    def active_program_setpoints(self) -> ProgramSetpoints | None:
        """Return the program setpoints of the side the zone control runs."""

        if self.is_using_derogated_temperature_fallback:
            return None

        return HVAC_MODE_TO_PROGRAM_SETPOINTS.get(cast(HVACMode, self.active_hvac_mode))

    @property
    def program_setpoints(self) -> ProgramSetpoints | None:
        """Return the program setpoints the zone applies, if it follows its program.

        A derogation overrides the program: the zone then applies the single
        derogation setpoint, like in manual mode.
        """

        if (program_setpoints := self.active_program_setpoints) is None:
            return None

        states = self.device.states

        if (
            states.get_value(program_setpoints.mode_state)
            != OverkizCommandParam.INTERNAL_SCHEDULING
            or states.get_value(OverkizState.CORE_DEROGATION_ON_OFF)
            == OverkizCommandParam.ON
        ):
            return None

        return program_setpoints

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the supported features, following the setpoints exposed."""

        supported_features = self._attr_supported_features

        if self.is_using_derogated_temperature_fallback:
            return supported_features

        # The range is the program and the single setpoint the manual one. Both
        # are accepted whatever the mode of the zone is: restoring a scene sets
        # the temperatures before the preset. A single setpoint needs a side to
        # write it to, so it is not offered while neither side is known.
        if self.device_hvac_mode is None:
            return supported_features

        supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        if (
            self.device_hvac_mode != HVACMode.HEAT_COOL
            or self.active_hvac_mode != HVACMode.HEAT_COOL
        ):
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        return supported_features

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""

        # When ZoneControl action is heating/cooling but Zone is
        # stopped, means the zone is idle.
        if (
            hvac_action := self.zone_control_hvac_action
        ) in HVAC_ACTION_TO_OVERKIZ_PROFILE_STATE and cast(
            str,
            self.device.states.get_value(
                HVAC_ACTION_TO_OVERKIZ_PROFILE_STATE[hvac_action]
            ),
        ) == OverkizCommandParam.STOP:
            return HVACAction.IDLE

        return hvac_action

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool, dry, off mode."""

        if self.is_using_derogated_temperature_fallback:
            return super().hvac_mode

        if (device_hvac_mode := self.device_hvac_mode) is None:
            return HVACMode.OFF

        cooling_is_off = cast(
            str,
            self.device.states.get_value(OverkizState.CORE_COOLING_ON_OFF),
        ) in (OverkizCommandParam.OFF, None)

        heating_is_off = cast(
            str,
            self.device.states.get_value(OverkizState.CORE_HEATING_ON_OFF),
        ) in (OverkizCommandParam.OFF, None)

        # Device is Stopped, it means the air flux is flowing
        # but its venting door is closed.
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

    @override
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

        await self.async_execute_and_refresh_modes(
            [
                Command(
                    name=OverkizCommand.SET_COOLING_ON_OFF,
                    parameters=[on_off_target_command_param],
                ),
                Command(
                    name=OverkizCommand.SET_HEATING_ON_OFF,
                    parameters=[on_off_target_command_param],
                ),
            ]
        )

    @property
    @override
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
                        cast(str, self.device.states.get_value(mode_state))
                    ]
                )
                is not None
            )
        ):
            return mode

        return PRESET_NONE

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        if self.is_using_derogated_temperature_fallback:
            await super().async_set_preset_mode(preset_mode)
            return

        mode = PRESET_MODES_TO_OVERKIZ[preset_mode]

        # A setpoint still waiting to be sent would start a derogation over the
        # mode chosen now.
        self.coordinator.discard_pending_commands(
            self.device_url,
            {
                OverkizCommand.SET_HEATING_TARGET_TEMPERATURE,
                OverkizCommand.SET_COOLING_TARGET_TEMPERATURE,
            },
        )

        # For consistency, it is better both are synced like on the Thermostat.
        commands = [
            Command(name=OverkizCommand.SET_PASS_APC_HEATING_MODE, parameters=[mode]),
            Command(name=OverkizCommand.SET_PASS_APC_COOLING_MODE, parameters=[mode]),
        ]

        # The zone keeps applying a derogation until it is turned off, even
        # once both modes follow the time program again. The state of the
        # derogation may not show one that has just been started, so it is
        # always turned off.
        if preset_mode == PRESET_SCHEDULE:
            commands.append(
                Command(
                    name=OverkizCommand.SET_DEROGATION_ON_OFF_STATE,
                    parameters=[OverkizCommandParam.OFF],
                )
            )

        await self.async_execute_and_refresh_modes(commands)

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return hvac target temperature."""

        if self.is_using_derogated_temperature_fallback:
            return super().native_target_temperature

        device_hvac_mode = self.active_hvac_mode

        if device_hvac_mode == HVACMode.HEAT_COOL or self.program_setpoints is not None:
            return None

        # A derogation over the program, started from a remote or the app, can
        # apply the setpoint of the other profile, which only the applied
        # setpoint reports. In manual mode the manual setpoint applies, and it
        # is up to date right after it is set, unlike the applied one.
        if (
            (program_setpoints := self.active_program_setpoints) is not None
            and self.device.states.get_value(program_setpoints.mode_state)
            == OverkizCommandParam.INTERNAL_SCHEDULING
            and self.device.states.get_value(OverkizState.CORE_DEROGATION_ON_OFF)
            == OverkizCommandParam.ON
            and (
                applied_target_temperature := self.device.states.get_value(
                    OverkizState.CORE_TARGET_TEMPERATURE
                )
            )
            is not None
        ):
            return cast(float, applied_target_temperature)

        if device_hvac_mode == HVACMode.COOL:
            return self.cooling_target_temperature

        if device_hvac_mode == HVACMode.HEAT:
            return self.heating_target_temperature

        return cast(
            float, self.device.states.get_value(OverkizState.CORE_TARGET_TEMPERATURE)
        )

    @property
    @override
    def native_target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach (cooling)."""

        if (program_setpoints := self.active_program_setpoints) is not None:
            return cast(
                float, self.device.states.get_value(program_setpoints.high_state)
            )

        if self.device_hvac_mode != HVACMode.HEAT_COOL:
            return None

        return self.cooling_target_temperature

    @property
    @override
    def native_target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach (heating)."""

        if (program_setpoints := self.active_program_setpoints) is not None:
            return cast(
                float, self.device.states.get_value(program_setpoints.low_state)
            )

        if self.device_hvac_mode != HVACMode.HEAT_COOL:
            return None

        return self.heating_target_temperature

    @property
    def heating_target_temperature(self) -> float | None:
        """Return the heating setpoint currently applied by the zone."""

        return self._active_target_temperature(
            OverkizState.IO_PASS_APC_HEATING_MODE,
            OverkizState.IO_PASS_APC_HEATING_PROFILE,
            HEATING_PROFILE_TO_TARGET_TEMPERATURE_STATE,
            OverkizState.CORE_HEATING_TARGET_TEMPERATURE,
        )

    @property
    def cooling_target_temperature(self) -> float | None:
        """Return the cooling setpoint currently applied by the zone."""

        return self._active_target_temperature(
            OverkizState.IO_PASS_APC_COOLING_MODE,
            OverkizState.IO_PASS_APC_COOLING_PROFILE,
            COOLING_PROFILE_TO_TARGET_TEMPERATURE_STATE,
            OverkizState.CORE_COOLING_TARGET_TEMPERATURE,
        )

    def _active_target_temperature(
        self,
        mode_state: OverkizState,
        profile_state: OverkizState,
        profile_to_target_temperature_state: dict[str, OverkizState],
        manual_target_temperature_state: OverkizState,
    ) -> float | None:
        """Return the program setpoint of the active profile when scheduled."""

        states = self.device.states

        # The manual setpoint applies outside the program and during a derogation.
        if (
            states.get_value(mode_state) == OverkizCommandParam.INTERNAL_SCHEDULING
            and states.get_value(OverkizState.CORE_DEROGATION_ON_OFF)
            != OverkizCommandParam.ON
            and (
                target_temperature_state := profile_to_target_temperature_state.get(
                    cast(str, states.get_value(profile_state))
                )
            )
            is not None
        ):
            return cast(float, states.get_value(target_temperature_state))

        return cast(float, states.get_value(manual_target_temperature_state))

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""

        if self.is_using_derogated_temperature_fallback:
            await super().async_set_temperature(**kwargs)
            return

        # The range is the eco and comfort setpoints of the program of the side
        # running. It never starts a derogation, whatever the mode of the zone.
        if (program_setpoints := self.active_program_setpoints) is not None:
            if program_commands := [
                Command(name=command, parameters=[target_temp])
                for command, target_temp in (
                    (program_setpoints.low_command, kwargs.get(ATTR_TARGET_TEMP_LOW)),
                    (
                        program_setpoints.high_command,
                        kwargs.get(ATTR_TARGET_TEMP_HIGH),
                    ),
                )
                if target_temp is not None
            ]:
                await self.async_execute_and_refresh_modes(
                    program_commands, _program_refresh_commands(program_commands)
                )

                # A saved state holds the range and the manual setpoint together.
                kwargs.pop(ATTR_TARGET_TEMP_LOW, None)
                kwargs.pop(ATTR_TARGET_TEMP_HIGH, None)
                if ATTR_TEMPERATURE not in kwargs:
                    return

            # While following the program, a single setpoint is only kept as the
            # manual one, which applies once the zone is switched to manual.
            if self.program_setpoints is not None:
                if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
                    await self.async_execute_and_refresh_modes(
                        [
                            Command(
                                name=(
                                    OverkizCommand.SET_HEATING_TARGET_TEMPERATURE
                                    if self.active_hvac_mode == HVACMode.HEAT
                                    else OverkizCommand.SET_COOLING_TARGET_TEMPERATURE
                                ),
                                parameters=[target_temperature],
                            )
                        ],
                        (),
                    )
                return

        # With no side running, the program has no setpoint to change, in any
        # mode: writing the manual setpoints instead would start a derogation.
        if self.active_hvac_mode not in (HVACMode.HEAT, HVACMode.COOL):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="zone_control_side_unknown",
            )

        # A single setpoint applies to the side currently running.
        if self.device_hvac_mode == HVACMode.HEAT_COOL and ATTR_TEMPERATURE in kwargs:
            active_target_temp = (
                ATTR_TARGET_TEMP_LOW
                if self.active_hvac_mode == HVACMode.HEAT
                else ATTR_TARGET_TEMP_HIGH
            )
            kwargs[active_target_temp] = kwargs.pop(ATTR_TEMPERATURE)

        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        # The setpoints are written even when the zone is off.
        hvac_mode = self.device_hvac_mode
        commands: list[Command] = []

        if hvac_mode == HVACMode.HEAT_COOL:
            if target_temp_low is not None:
                commands.append(
                    Command(
                        name=OverkizCommand.SET_HEATING_TARGET_TEMPERATURE,
                        parameters=[target_temp_low],
                    )
                )

            if target_temp_high is not None:
                commands.append(
                    Command(
                        name=OverkizCommand.SET_COOLING_TARGET_TEMPERATURE,
                        parameters=[target_temp_high],
                    )
                )

        elif target_temperature is not None:
            if hvac_mode == HVACMode.HEAT:
                commands.append(
                    Command(
                        name=OverkizCommand.SET_HEATING_TARGET_TEMPERATURE,
                        parameters=[target_temperature],
                    )
                )

            elif hvac_mode == HVACMode.COOL:
                commands.append(
                    Command(
                        name=OverkizCommand.SET_COOLING_TARGET_TEMPERATURE,
                        parameters=[target_temperature],
                    )
                )

        # The derogation only has to be started once: sending it again with
        # every step of the slider and refreshing the modes makes each step
        # slower, and a long queue of steps loses commands.
        if (
            self.device.states.get_value(OverkizState.CORE_DEROGATION_ON_OFF)
            == OverkizCommandParam.ON
        ):
            # A derogation over the program shows the applied setpoint, which
            # only changes once it is refreshed. A manual zone shows the one
            # that has just been written.
            await self.async_execute_and_refresh_modes(
                commands,
                (
                    (OverkizCommand.REFRESH_TARGET_TEMPERATURE,)
                    if (program_setpoints := self.active_program_setpoints) is not None
                    and self.device.states.get_value(program_setpoints.mode_state)
                    == OverkizCommandParam.INTERNAL_SCHEDULING
                    else ()
                ),
            )
            return

        commands.append(
            Command(
                name=OverkizCommand.SET_DEROGATION_ON_OFF_STATE,
                parameters=[OverkizCommandParam.ON],
            )
        )

        await self.async_execute_and_refresh_modes(commands)

    async def async_execute_and_refresh_modes(
        self,
        commands: list[Command],
        refresh: tuple[OverkizCommand, ...] = REFRESH_MODES_COMMANDS,
    ) -> None:
        """Execute commands, then refresh the states they change."""

        # Commands of one execution run in order, so the refreshes only start
        # once the device has applied the previous commands. Each command takes
        # seconds on the device, and a long queue makes it drop commands.
        # The device refuses calls sent too quickly: while a write of the same
        # setting is running, only the latest value is kept and sent after it.
        await self.executor.async_execute_commands(
            [*commands, *(Command(name=name) for name in refresh)], coalesce=True
        )

    @property
    @override
    def min_temp(self) -> float:
        """Return Minimum Temperature for AC of this group."""

        device_hvac_mode = self.active_hvac_mode

        if device_hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            return cast(
                float,
                self.device.states.get_value(
                    OverkizState.CORE_MINIMUM_HEATING_TARGET_TEMPERATURE
                ),
            )

        if device_hvac_mode == HVACMode.COOL:
            return cast(
                float,
                self.device.states.get_value(
                    OverkizState.CORE_MINIMUM_COOLING_TARGET_TEMPERATURE
                ),
            )

        return super().min_temp

    @property
    @override
    def max_temp(self) -> float:
        """Return Max Temperature for AC of this group."""

        device_hvac_mode = self.active_hvac_mode

        if device_hvac_mode == HVACMode.HEAT:
            return cast(
                float,
                self.device.states.get_value(
                    OverkizState.CORE_MAXIMUM_HEATING_TARGET_TEMPERATURE
                ),
            )

        if device_hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL):
            return cast(
                float,
                self.device.states.get_value(
                    OverkizState.CORE_MAXIMUM_COOLING_TARGET_TEMPERATURE
                ),
            )

        return super().max_temp
