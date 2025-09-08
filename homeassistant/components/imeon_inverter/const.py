"""Constant for Imeon component."""

from homeassistant.const import Platform

DOMAIN = "imeon_inverter"
TIMEOUT = 30
PLATFORMS = [
    Platform.SENSOR,
]
ATTR_BATTERY_STATUS = ["charging", "discharging", "charged"]
ATTR_INVERTER_STATE = [
    "not_connected",
    "unsynchronized",
    "grid_consumption",
    "grid_injection",
    "grid_synchronized_but_not_used",
]
ATTR_TIMELINE_STATUS = [
    "com_lost",
    "warning_grid",
    "warning_pv",
    "warning_bat",
    "error_ond",
    "error_soft",
    "error_pv",
    "error_grid",
    "error_bat",
    "good_1",
    "info_soft",
    "info_ond",
    "info_bat",
    "info_smartlo",
]
