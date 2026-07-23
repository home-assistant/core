"""Isolated mappings for NuHeat behavior that still needs live validation."""

from chemelex_nuheat import ScheduleMode, ThermostatMode

from homeassistant.components.climate import HVACMode

from .const import PRESET_MANUAL, PRESET_RUN, PRESET_TEMPORARY_HOLD

MODE_TO_PRESET = {
    ThermostatMode.AUTO: PRESET_RUN,
    ThermostatMode.HOLD: PRESET_TEMPORARY_HOLD,
    ThermostatMode.MANUAL: PRESET_MANUAL,
}
PRESET_TO_MODE = {
    PRESET_RUN: ScheduleMode.AUTO,
    PRESET_TEMPORARY_HOLD: ScheduleMode.HOLD,
    PRESET_MANUAL: ScheduleMode.MANUAL,
}


def is_supported_api_mode(mode: int) -> bool:
    """Return whether a provisional v2 integer mode has a safe mapping."""
    try:
        ThermostatMode(mode)
    except ValueError:
        return False
    return True


def preset_for_api_mode(mode: int) -> str | None:
    """Map a provisional reported v2 mode without disguising unknown values."""
    try:
        return MODE_TO_PRESET[ThermostatMode(mode)]
    except ValueError, KeyError:
        return None


def api_mode_for_preset(preset: str) -> ScheduleMode:
    """Map a supported Home Assistant preset to a v2 mode command."""
    try:
        return PRESET_TO_MODE[preset]
    except KeyError as err:
        raise ValueError(f"Unsupported preset mode: {preset}") from err


def hvac_mode_for_api_mode(mode: int) -> HVACMode | None:
    """Map scheduled operation to AUTO and distinct Manual operation to HEAT."""
    try:
        thermostat_mode = ThermostatMode(mode)
    except ValueError:
        return None
    return HVACMode.HEAT if thermostat_mode is ThermostatMode.MANUAL else HVACMode.AUTO


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

    Changing a setpoint during scheduled operation uses the documented Hold
    command, while Manual/HEAT remains Manual. The v2 response values and Hold
    expiration semantics still require live validation.
    """
    if requested_hvac_mode is HVACMode.HEAT:
        return ScheduleMode.MANUAL
    try:
        if ThermostatMode(current_mode) is ThermostatMode.MANUAL:
            return ScheduleMode.MANUAL
    except ValueError as err:
        raise ValueError(f"Unsupported API mode: {current_mode}") from err
    return ScheduleMode.HOLD
