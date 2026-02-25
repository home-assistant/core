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


T2253_MAPPING = RoboVacModelMapping(
    model_code="T2253",
    display_name="G30 Hybrid",
    commands={
        RoboVacCommand.START_PAUSE: 2,
        RoboVacCommand.DIRECTION: 3,
        RoboVacCommand.MODE: 5,
        RoboVacCommand.STATUS: 15,
        RoboVacCommand.RETURN_HOME: 101,
        RoboVacCommand.FAN_SPEED: 102,
        RoboVacCommand.LOCATE: 103,
        RoboVacCommand.BATTERY: 104,
        RoboVacCommand.ERROR: 106,
    },
    mode_values={
        "auto": "Auto",
        "small_room": "SmallRoom",
        "spot": "Spot",
        "edge": "Edge",
        "nosweep": "Nosweep",
    },
    fan_speed_values={
        "standard": "Standard",
        "turbo": "Turbo",
        "max": "Max",
        "boost_iq": "Boost_IQ",
    },
    error_values={
        "0": "No error",
    },
)


MODEL_MAPPINGS: dict[str, RoboVacModelMapping] = {
    T2253_MAPPING.model_code: T2253_MAPPING,
}
