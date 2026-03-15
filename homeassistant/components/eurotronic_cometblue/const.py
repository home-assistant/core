"""Constants for Cometblue BLE thermostats."""

from typing import Final

DOMAIN: Final = "eurotronic_cometblue"

CONF_ALL_TEMPERATURES: Final = {
    "currentTemp",
    "manualTemp",
    "targetTempLow",
    "targetTempHigh",
    "tempOffset",
    "windowOpen",
    "windowOpenMinutes",
}

MAX_RETRIES: Final = 3
