"""Model command mappings for Eufy RoboVac devices.

These mappings define how Home Assistant-facing command keys map to
model-specific local protocol values.
"""

from dataclasses import dataclass

from .const import RoboVacCommand


@dataclass(frozen=True, kw_only=True)
class RoboVacModelMapping:
    """Command mapping details for a RoboVac model."""

    model_code: str
    display_name: str
    commands: dict[RoboVacCommand, int]
    mode_values: dict[str, str]
    fan_speed_values: dict[str, str]
    error_values: dict[str, str]


DEFAULT_COMMAND_CODES: dict[RoboVacCommand, int] = {
    RoboVacCommand.START_PAUSE: 2,
    RoboVacCommand.DIRECTION: 3,
    RoboVacCommand.MODE: 5,
    RoboVacCommand.STATUS: 15,
    RoboVacCommand.RETURN_HOME: 101,
    RoboVacCommand.FAN_SPEED: 102,
    RoboVacCommand.LOCATE: 103,
    RoboVacCommand.BATTERY: 104,
    RoboVacCommand.ERROR: 106,
}

DEFAULT_MODE_VALUES: dict[str, str] = {
    "auto": "Auto",
    "small_room": "SmallRoom",
    "spot": "Spot",
    "edge": "Edge",
    "nosweep": "Nosweep",
}

DEFAULT_FAN_SPEED_VALUES: dict[str, str] = {
    "standard": "Standard",
    "turbo": "Turbo",
    "max": "Max",
    "boost_iq": "Boost_IQ",
}

PURE_FAN_SPEED_VALUES: dict[str, str] = {
    "pure": "Quiet",
    "standard": "Standard",
    "turbo": "Turbo",
    "max": "Max",
}

QUIET_FAN_SPEED_VALUES: dict[str, str] = {
    "quiet": "Quiet",
    "standard": "Standard",
    "turbo": "Turbo",
    "max": "Max",
}

DEFAULT_ERROR_VALUES: dict[str, str] = {
    "0": "No error",
}


def _build_mapping(
    *,
    model_code: str,
    display_name: str,
    command_overrides: dict[RoboVacCommand, int] | None = None,
    mode_values: dict[str, str] | None = None,
    fan_speed_values: dict[str, str] | None = None,
    error_values: dict[str, str] | None = None,
) -> RoboVacModelMapping:
    """Build a model mapping from the shared baseline plus per-model overrides."""
    return RoboVacModelMapping(
        model_code=model_code,
        display_name=display_name,
        commands={
            **DEFAULT_COMMAND_CODES,
            **(command_overrides or {}),
        },
        mode_values=mode_values or DEFAULT_MODE_VALUES,
        fan_speed_values=fan_speed_values or DEFAULT_FAN_SPEED_VALUES,
        error_values=error_values or DEFAULT_ERROR_VALUES,
    )


MODEL_MAPPINGS: dict[str, RoboVacModelMapping] = {
    # High-confidence mappings validated with this integration's test suite.
    "T2118": _build_mapping(model_code="T2118", display_name="RoboVac 30C"),
    "T2128": _build_mapping(
        model_code="T2128",
        display_name="RoboVac 15C Max",
        fan_speed_values=QUIET_FAN_SPEED_VALUES,
    ),
    "T2181": _build_mapping(
        model_code="T2181",
        display_name="RoboVac G20",
        fan_speed_values=PURE_FAN_SPEED_VALUES,
    ),
    "T2193": _build_mapping(
        model_code="T2193",
        display_name="RoboVac LR30 Hybrid",
        fan_speed_values=PURE_FAN_SPEED_VALUES,
    ),
    "T2194": _build_mapping(
        model_code="T2194",
        display_name="RoboVac L35 Hybrid",
        command_overrides={RoboVacCommand.FAN_SPEED: 130},
        fan_speed_values=QUIET_FAN_SPEED_VALUES,
    ),
    "T2251": _build_mapping(model_code="T2251", display_name="RoboVac G30 Edge"),
    "T2252": _build_mapping(model_code="T2252", display_name="RoboVac G30 Verge"),
    "T2253": _build_mapping(model_code="T2253", display_name="G30 Hybrid"),
    "T2254": _build_mapping(
        model_code="T2254",
        display_name="RoboVac G20 Hybrid",
    ),
    "T2255": _build_mapping(model_code="T2255", display_name="RoboVac G35+"),
    "T2259": _build_mapping(model_code="T2259", display_name="RoboVac G40+"),
    "T2261": _build_mapping(
        model_code="T2261",
        display_name="RoboVac X8",
        fan_speed_values=PURE_FAN_SPEED_VALUES,
    ),
    "T2262": _build_mapping(
        model_code="T2262",
        display_name="RoboVac X8 Hybrid",
        fan_speed_values=PURE_FAN_SPEED_VALUES,
    ),
    "T2268": _build_mapping(
        model_code="T2268",
        display_name="RoboVac LR30 Hybrid+",
        fan_speed_values=PURE_FAN_SPEED_VALUES,
    ),
}
