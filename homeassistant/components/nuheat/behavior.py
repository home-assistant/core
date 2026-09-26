"""Map live-validated NuHeat read states separately from write commands."""

from chemelex_nuheat import ScheduleMode, Thermostat, ThermostatState

from homeassistant.components.climate import HVACMode

from .const import PRESET_RUN, PRESET_TEMPORARY_HOLD

STATE_TO_PRESET = {
    ThermostatState.SCHEDULED: PRESET_RUN,
    ThermostatState.TIMED_HOLD: PRESET_TEMPORARY_HOLD,
}
PRESET_TO_MODE = {
    PRESET_RUN: ScheduleMode.AUTO,
    PRESET_TEMPORARY_HOLD: ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE,
}


def preset_for_thermostat(thermostat: Thermostat) -> str | None:
    """Return a preset only when the complete response supports one."""
    return STATE_TO_PRESET.get(thermostat.state)


def api_mode_for_preset(preset: str) -> ScheduleMode:
    """Map presets with validated command behavior to v2 commands.

    Permanent Hold is reported as a preset, but selecting it remains blocked
    until its documented request contract is known. Hold without an expiration
    is verified to mean hold until the next scheduled event.
    """
    try:
        return PRESET_TO_MODE[preset]
    except KeyError as err:
        raise ValueError(f"Unsupported preset mode: {preset}") from err


def hvac_mode_for_thermostat(thermostat: Thermostat) -> HVACMode | None:
    """Map the corrected GET state while preserving unresolved ambiguity."""
    if thermostat.state is ThermostatState.STANDBY:
        return HVACMode.OFF
    if thermostat.state in (
        ThermostatState.SCHEDULED,
        ThermostatState.TIMED_HOLD,
    ):
        return HVACMode.AUTO
    if thermostat.state is ThermostatState.AMBIGUOUS_MANUAL_OR_PERMANENT_HOLD:
        return HVACMode.HEAT
    return None


def api_mode_for_hvac_mode(hvac_mode: HVACMode) -> ScheduleMode:
    """Map the existing public HVAC command contract to documented commands.

    Auto is verified to resume the schedule and exit Hold, Manual, or Standby.
    """
    if hvac_mode is HVACMode.AUTO:
        return ScheduleMode.AUTO
    if hvac_mode is HVACMode.HEAT:
        return ScheduleMode.MANUAL
    raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")


def setpoint_command_mode(
    thermostat: Thermostat, requested_hvac_mode: HVACMode | None = None
) -> ScheduleMode:
    """Choose a command without deriving it from the numeric mode alone.

    An explicit HEAT request retains the existing documented Manual command.
    Scheduled operation uses Hold-until-next-schedule for a setpoint change.
    An existing timed hold keeps its explicit end in the entity write path.
    The mode-3 Manual/permanent-hold overlap uses Manual for setpoint changes;
    both states are constant-target heating rather than scheduled operation.
    Standby and unknown responses require an explicit command.
    """
    if requested_hvac_mode is HVACMode.HEAT:
        return ScheduleMode.MANUAL
    if thermostat.state in (
        ThermostatState.SCHEDULED,
        ThermostatState.TIMED_HOLD,
    ):
        return ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE
    if thermostat.state is ThermostatState.AMBIGUOUS_MANUAL_OR_PERMANENT_HOLD:
        return ScheduleMode.MANUAL
    raise ValueError(f"Unsupported thermostat state: {thermostat.state}")
