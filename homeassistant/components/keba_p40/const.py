"""Constants for the KEBA P40 integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "keba_p40"
MANUFACTURER = "KEBA"
DEFAULT_PORT = 8443
SCAN_INTERVAL = timedelta(seconds=30)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
