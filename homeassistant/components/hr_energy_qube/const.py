"""Constants for the Qube Heat Pump integration."""

from homeassistant.const import Platform

DOMAIN = "hr_energy_qube"
PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
)

DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 15
