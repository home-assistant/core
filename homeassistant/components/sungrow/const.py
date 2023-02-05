"""Constants for the Sungrow Solar Energy integration."""
from __future__ import annotations

DOMAIN = "sungrow"

BATTERY_DEVICE_VARIABLES: list[str] = [
    "battery_voltage",
    "battery_current",
    "battery_power",
    "battery_level",
    "battery_health",
    "battery_temperature",
    "daily_battery_discharge_energy",
    "total_battery_discharge_energy",
    "battery_capacity",
    "battery_maintenance",
    "battery_type",
    "battery_nominal_voltage",
    "charge_discharge",
    "charge_discharge_command",
    "max_soc",
    "min_soc",
    "reserved_soc_for_backup",
    "battery_over_voltage_threshold",
    "battery_under_voltage_threshold",
    "battery_over_temperature_threshold",
    "battery_under_temperature_threshold",
]
