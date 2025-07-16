"""Constants for niko_home_control integration."""

from enum import IntEnum

DOMAIN = "niko_home_control"

NIKO_HOME_CONTROL_THERMOSTAT_MODES_MAP = {
    "off": 3,
    "cool": 4,
    "auto": 5,
}
NIKO_HOME_CONTROL_THERMOSTAT_MODES = IntEnum(
    "NIKO_HOME_CONTROL_THERMOSTAT_MODES",
    {
        "OFF": 3,
        "COOL": 4,
        "AUTO": 5,
    },
)
