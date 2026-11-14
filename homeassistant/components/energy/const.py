"""Constants for the Energy integration."""

from typing import Literal

DOMAIN = "energy"

type BatteryDirection = tuple[
    Literal[
        "stat_energy_from_grid",
        "stat_energy_from_solar",
        "stat_energy_to_home",
        "stat_energy_to_grid",
    ],
    Literal[
        "stat_rate_from_grid",
        "stat_rate_from_solar",
        "stat_rate_to_home",
        "stat_rate_to_grid",
    ],
]

# Energy and power keys of a battery measured per direction
BATTERY_CHARGE_DIRECTIONS: tuple[BatteryDirection, ...] = (
    ("stat_energy_from_grid", "stat_rate_from_grid"),
    ("stat_energy_from_solar", "stat_rate_from_solar"),
)
BATTERY_DISCHARGE_DIRECTIONS: tuple[BatteryDirection, ...] = (
    ("stat_energy_to_home", "stat_rate_to_home"),
    ("stat_energy_to_grid", "stat_rate_to_grid"),
)
BATTERY_DIRECTIONS = BATTERY_CHARGE_DIRECTIONS + BATTERY_DISCHARGE_DIRECTIONS
