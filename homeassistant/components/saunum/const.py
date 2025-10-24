"""Constants for the Saunum Leil Sauna Control Unit integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "saunum"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
]

DEFAULT_DEVICE_ID: Final = 1
DEFAULT_PORT: Final = 502
DEFAULT_SCAN_INTERVAL: Final = 5

# Modbus register addresses - Holding Registers (Read/Write)
REG_SESSION_ACTIVE: Final = 0
REG_TARGET_TEMPERATURE: Final = 4

# Read-only registers - Input Registers
REG_CURRENT_TEMP: Final = 100

# Value ranges - Celsius (device native)
MIN_TEMPERATURE_C: Final = 40
MAX_TEMPERATURE_C: Final = 100
DEFAULT_TEMPERATURE_C: Final = 80

# Value ranges - Fahrenheit (for display)
MIN_TEMPERATURE_F: Final = 104  # 40°C
MAX_TEMPERATURE_F: Final = 212  # 100°C
DEFAULT_TEMPERATURE_F: Final = 176  # 80°C

# Write settle delay (seconds) to allow device to apply register changes before refresh
WRITE_SETTLE_SECONDS: Final = 1
