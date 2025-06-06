"""Constant for Imeon component."""

from homeassistant.const import Platform

DOMAIN = "imeon_inverter"
TIMEOUT = 30
PLATFORMS = [
    Platform.SELECT,
    Platform.SENSOR,
]
ATTR_BATTERY_STATUS = ["charging", "discharging", "charged"]
ATTR_INVERTER_MODE = ["smg", "bup", "ong", "ofg"]
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
TIMELINE_ICONS = {
    "com_lost": "mdi:lan-disconnect",
    "com_ok": "mdi:lan-connect",
    "warning_grid": "mdi:alert-circle",
    "warning_ond": "mdi:alert-circle",
    "warning_soft": "mdi:alert-circle",
    "warning_pv": "mdi:alert-circle",
    "warning_bat": "mdi:alert-circle",
    "warning_cpu": "mdi:alert-circle",
    "warning_spe": "mdi:alert-circle",
    "error_grid": "mdi:close-octagon",
    "error_ond": "mdi:close-octagon",
    "error_soft": "mdi:close-octagon",
    "error_pv": "mdi:close-octagon",
    "error_bat": "mdi:close-octagon",
    "error_spe": "mdi:close-octagon-outline",
    "info_grid": "mdi:information-slab-circle",
    "info_ond": "mdi:information-slab-circle",
    "info_soft": "mdi:information-slab-circle",
    "info_pv": "mdi:information-slab-circle",
    "info_bat": "mdi:information-slab-circle",
    "info_cpu": "mdi:information-slab-circle",
    "info_spe": "mdi:information-slab-circle",
    "warning_unknown": "mdi:alert",
    "warnings": "mdi:alert",
    "error_unknown": "mdi:close-octagon",
    "errors": "mdi:close-octagon",
    "good_1": "mdi:check-circle",
    "good_2": "mdi:check-circle",
    "good_3": "mdi:check-circle",
}
