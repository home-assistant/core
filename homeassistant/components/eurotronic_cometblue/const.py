"""Constants for Cometblue BLE thermostats."""

from typing import Final

DOMAIN: Final = "eurotronic_cometblue"
DEFAULT_NAME: Final = "Eurotronic Comet Blue"

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
