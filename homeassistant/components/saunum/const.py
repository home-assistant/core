"""Constants for the Saunum Leil Sauna Control Unit integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "saunum"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Configuration constants
CONF_SAUNA_TYPE_1_NAME: Final = "sauna_type_1_name"
CONF_SAUNA_TYPE_2_NAME: Final = "sauna_type_2_name"
CONF_SAUNA_TYPE_3_NAME: Final = "sauna_type_3_name"

DEFAULT_DEVICE_ID: Final = 1
DEFAULT_PORT: Final = 502
DEFAULT_SCAN_INTERVAL: Final = 5
DEFAULT_SAUNA_TYPE_1_NAME: Final = "Sauna type 1"
DEFAULT_SAUNA_TYPE_2_NAME: Final = "Sauna type 2"
DEFAULT_SAUNA_TYPE_3_NAME: Final = "Sauna type 3"

# Modbus register addresses - Holding Registers (Read/Write)
REG_SESSION_ACTIVE: Final = 0
REG_SAUNA_TYPE: Final = 1
REG_SAUNA_DURATION: Final = 2
REG_FAN_DURATION: Final = 3
REG_TARGET_TEMPERATURE: Final = 4
REG_FAN_SPEED: Final = 5
REG_LIGHT: Final = 6

# Read-only registers - Input Registers
REG_CURRENT_TEMP: Final = 100
REG_ON_TIME_HIGH: Final = 101
REG_ON_TIME_LOW: Final = 102
REG_HEATER_STATUS: Final = 103
REG_DOOR_STATUS: Final = 104

# Alarm registers
REG_ALARM_DOOR_OPEN: Final = 200
REG_ALARM_DOOR_SENSOR: Final = 201
REG_ALARM_THERMAL_CUTOFF: Final = 202
REG_ALARM_INTERNAL_TEMP: Final = 203
REG_ALARM_TEMP_SENSOR_SHORTED: Final = 204
REG_ALARM_TEMP_SENSOR_NOT_CONNECTED: Final = 205

# Value ranges - Celsius (device native)
MIN_TEMPERATURE_C: Final = 40
MAX_TEMPERATURE_C: Final = 100
DEFAULT_TEMPERATURE_C: Final = 80

# Value ranges - Fahrenheit (for display)
MIN_TEMPERATURE_F: Final = 104  # 40°C
MAX_TEMPERATURE_F: Final = 212  # 100°C
DEFAULT_TEMPERATURE_F: Final = 176  # 80°C

MIN_DURATION: Final = 0
MAX_DURATION: Final = 720
DEFAULT_DURATION: Final = 120

MIN_FAN_DURATION: Final = 0
MAX_FAN_DURATION: Final = 30
DEFAULT_FAN_DURATION: Final = 15

MIN_FAN_SPEED: Final = 0
MAX_FAN_SPEED: Final = 3
DEFAULT_FAN_SPEED: Final = 1

# Write settle delay (seconds) to allow device to apply register changes before refresh
WRITE_SETTLE_SECONDS: Final = 1

# Sauna types
SAUNA_TYPE_1: Final = 0
SAUNA_TYPE_2: Final = 1
SAUNA_TYPE_3: Final = 2

# Sauna type ranges
MIN_SAUNA_TYPE: Final = 0
MAX_SAUNA_TYPE: Final = 2
DEFAULT_SAUNA_TYPE: Final = SAUNA_TYPE_1
