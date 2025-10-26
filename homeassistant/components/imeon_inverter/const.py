"""Constant for Imeon component."""

from homeassistant.const import Platform

DOMAIN = "imeon_inverter"
TIMEOUT = 30
PLATFORMS = [
    Platform.SELECT,
    Platform.SENSOR,
]
ATTR_BATTERY_STATUS = ["charging", "discharging", "charged"]
ATTR_INVERTER_MODE = {
    "smg": "smart_grid",
    "bup": "backup",
    "ong": "on_grid",
    "ofg": "off_grid",
}
INVERTER_MODE_OPTIONS = {v: k for k, v in ATTR_INVERTER_MODE.items()}
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
