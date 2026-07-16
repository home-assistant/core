"""Isolated mappings for NuHeat behavior that still needs live validation."""

from chemelex_nuheat import ScheduleMode, ThermostatMode

from homeassistant.components.climate import HVACMode

from .const import PRESET_PERMANENT_HOLD, PRESET_RUN, PRESET_TEMPORARY_HOLD

MODE_TO_PRESET = {
    ThermostatMode.AUTO: PRESET_RUN,
    ThermostatMode.HOLD: PRESET_TEMPORARY_HOLD,
    ThermostatMode.MANUAL: PRESET_PERMANENT_HOLD,
}
PRESET_TO_MODE = {
    PRESET_RUN: ScheduleMode.AUTO,
    PRESET_TEMPORARY_HOLD: ScheduleMode.HOLD,
    PRESET_PERMANENT_HOLD: ScheduleMode.MANUAL,
}


def preset_for_api_mode(mode: int) -> str:
    """Map a reported v2 integer mode to a Home Assistant preset."""
    try:
        return MODE_TO_PRESET[ThermostatMode(mode)]
    except ValueError, KeyError:
        return PRESET_PERMANENT_HOLD


def api_mode_for_preset(preset: str) -> ScheduleMode:
    """Map a supported Home Assistant preset to a v2 mode command."""
    try:
        return PRESET_TO_MODE[preset]
    except KeyError as err:
        raise ValueError(f"Unsupported preset mode: {preset}") from err


def hvac_mode_for_api_mode(mode: int) -> HVACMode:
    """Map API Auto to AUTO and both hold modes to legacy HEAT."""
    try:
        return (
            HVACMode.AUTO
            if ThermostatMode(mode) is ThermostatMode.AUTO
            else HVACMode.HEAT
        )
    except ValueError:
        return HVACMode.HEAT


def api_mode_for_hvac_mode(hvac_mode: HVACMode) -> ScheduleMode:
    """Map the legacy public HVAC contract to OpenAPI v2 commands."""
    if hvac_mode is HVACMode.AUTO:
        return ScheduleMode.AUTO
    if hvac_mode is HVACMode.HEAT:
        return ScheduleMode.MANUAL
    raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")


def setpoint_command_mode(
    current_mode: int, requested_hvac_mode: HVACMode | None = None
) -> ScheduleMode:
    """Choose temporary Hold or Manual for a target-temperature write.

    The legacy entity behaves like the thermostat UI: changing a setpoint while
    running a schedule creates a temporary hold, while permanent hold/HEAT stays
    Manual. The v2 Hold expiration semantics still require live validation.
    """
    if requested_hvac_mode is HVACMode.HEAT:
        return ScheduleMode.MANUAL
    try:
        if ThermostatMode(current_mode) is ThermostatMode.MANUAL:
            return ScheduleMode.MANUAL
    except ValueError:
        return ScheduleMode.MANUAL
    return ScheduleMode.HOLD
