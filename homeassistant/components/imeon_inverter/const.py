"""Constant for Imeon component."""

from homeassistant.const import Platform

DOMAIN = "imeon_inverter"
TIMEOUT = 30
PLATFORMS = [
    Platform.SENSOR,
]
ATTR_BATTERY_STATUS = ["charging", "discharging", "charged"]
ATTR_INVERTER_STATE = [
    "unsynchronised",
    "grid_consumption",
    "grid_injection",
    "grid_synchronised_but_not_used",
]
ATTR_TIMELINE_STATUS = [
    "com_lost",
    "com_ok",
    "warning_grid",
    "warning_ond",
    "warning_soft",
    "warning_pv",
    "warning_bat",
    "warning_cpu",
    "warning_spe",
    "error_grid",
    "error_ond",
    "error_soft",
    "error_pv",
    "error_bat",
    "error_spe",
    "info_grid",
    "info_ond",
    "info_soft",
    "info_pv",
    "info_bat",
    "info_cpu",
    "info_spe",
    "warning_unknown",
    "warnings",
    "error_unknown",
    "errors",
    "good_1",
    "good_2",
    "good_3",
]
