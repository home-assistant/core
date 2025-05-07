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
