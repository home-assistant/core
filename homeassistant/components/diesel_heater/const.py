"""Constants for the Diesel Heater integration."""
from typing import Final

# Re-export all protocol constants from the diesel-heater-ble PyPI package.
# This allows entity files to keep using `from .const import X` unchanged.
from diesel_heater_ble.const import (  # noqa: F401
    ABBA_CMD_AUTO,
    ABBA_CMD_CONST_TEMP,
    ABBA_CMD_GET_AUTO_CONFIG,
    ABBA_CMD_GET_TIME,
    ABBA_CMD_HEAT_OFF,
    ABBA_CMD_HEAT_ON,
    ABBA_CMD_HIGH_ALTITUDE,
    ABBA_CMD_OTHER_MODE,
    ABBA_CMD_STATUS,
    ABBA_CMD_TEMP_DOWN,
    ABBA_CMD_TEMP_UP,
    ABBA_CMD_VENTILATION,
    ABBA_ERROR_NAMES,
    ABBA_STATUS_MAP,
    CBFF_RUN_STATE_OFF,
    ENCRYPTION_KEY,
    ERROR_NAMES,
    ERROR_NONE,
    MAX_LEVEL,
    MAX_TEMP_CELSIUS,
    MIN_LEVEL,
    MIN_TEMP_CELSIUS,
    PROTOCOL_HEADER_AA55,
    PROTOCOL_HEADER_AA66,
    PROTOCOL_HEADER_AA77,
    PROTOCOL_HEADER_ABBA,
    PROTOCOL_HEADER_BAAB,
    PROTOCOL_HEADER_CBFF,
    RUNNING_MODE_LEVEL,
    RUNNING_MODE_MANUAL,
    RUNNING_MODE_NAMES,
    RUNNING_MODE_TEMPERATURE,
    RUNNING_MODE_VENTILATION,
    RUNNING_STATE_OFF,
    RUNNING_STATE_ON,
    RUNNING_STEP_COOLDOWN,
    RUNNING_STEP_IGNITION,
    RUNNING_STEP_NAMES,
    RUNNING_STEP_RUNNING,
    RUNNING_STEP_SELF_TEST,
    RUNNING_STEP_STANDBY,
    RUNNING_STEP_VENTILATION,
)

# ---------------------------------------------------------------------------
# Integration-specific constants (Home Assistant only)
# ---------------------------------------------------------------------------

DOMAIN: Final = "diesel_heater"

# Old domain for migration from previous versions
OLD_DOMAIN: Final = "vevor_heater"

# BLE Service and Characteristic UUIDs
# Some heaters use ffe0 instead of fff0
SERVICE_UUID: Final = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID: Final = "0000ffe1-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID: Final = "0000ffe2-0000-1000-8000-00805f9b34fb"

# Alternative UUIDs (fff0 variant)
SERVICE_UUID_ALT: Final = "0000fff0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID_ALT: Final = "0000fff1-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID_ALT: Final = "0000fff2-0000-1000-8000-00805f9b34fb"

# ABBA Protocol (HeaterCC heaters)
# These heaters use service fff0 with characteristics fff1 (notify) and fff2 (write)
ABBA_SERVICE_UUID: Final = "0000fff0-0000-1000-8000-00805f9b34fb"
ABBA_NOTIFY_UUID: Final = "0000fff1-0000-1000-8000-00805f9b34fb"
ABBA_WRITE_UUID: Final = "0000fff2-0000-1000-8000-00805f9b34fb"

# Temperature calibration
CONF_TEMPERATURE_OFFSET: Final = "temperature_offset"
DEFAULT_TEMPERATURE_OFFSET: Final = 0.0
MIN_TEMPERATURE_OFFSET: Final = -20.0
MAX_TEMPERATURE_OFFSET: Final = 20.0
SENSOR_TEMP_MIN: Final = -128
SENSOR_TEMP_MAX: Final = 127

# BLE authentication PIN
CONF_PIN: Final = "pin"
DEFAULT_PIN: Final = 1234
MIN_PIN: Final = 0
MAX_PIN: Final = 9999

# Climate presets
CONF_PRESET_AWAY_TEMP: Final = "preset_away_temp"
CONF_PRESET_COMFORT_TEMP: Final = "preset_comfort_temp"
DEFAULT_PRESET_AWAY_TEMP: Final = 8
DEFAULT_PRESET_COMFORT_TEMP: Final = 21

# Heater temperature offset (sent to heater via cmd 20)
MIN_HEATER_OFFSET: Final = -9
MAX_HEATER_OFFSET: Final = 9

# Configuration settings commands (verified by @Xev testing)
CMD_SET_LANGUAGE: Final = 14
CMD_SET_TEMP_UNIT: Final = 15
CMD_SET_TANK_VOLUME: Final = 16  # Index-based: 0=None, 1=5L, 2=10L, etc.
CMD_SET_PUMP_TYPE: Final = 17
CMD_SET_ALTITUDE_UNIT: Final = 19
CMD_SET_OFFSET: Final = 20
CMD_SET_BACKLIGHT: Final = 21

# Language options (byte 26)
LANGUAGE_OPTIONS: Final = {
    0: "English",
    1: "Chinese",
    2: "German",
    3: "Silent",
    4: "Russian",
}

# Temperature unit (byte 27)
TEMP_UNIT_CELSIUS: Final = 0
TEMP_UNIT_FAHRENHEIT: Final = 1

# Altitude unit (byte 30)
ALTITUDE_UNIT_METERS: Final = 0
ALTITUDE_UNIT_FEET: Final = 1

# Tank volume range (byte 28) - index-based, not liters!
MIN_TANK_VOLUME: Final = 0
MAX_TANK_VOLUME: Final = 10

# Tank volume options - INDEX-BASED
TANK_VOLUME_OPTIONS: Final = {
    0: "None",
    1: "5 L",
    2: "10 L",
    3: "15 L",
    4: "20 L",
    5: "25 L",
    6: "30 L",
    7: "35 L",
    8: "40 L",
    9: "45 L",
    10: "50 L",
}

# Pump type options (byte 29)
PUMP_TYPE_OPTIONS: Final = {
    0: "16\u00b5l",
    1: "22\u00b5l",
    2: "28\u00b5l",
    3: "32\u00b5l",
}

# Backlight brightness options
BACKLIGHT_OPTIONS: Final = {
    0: "Off",
    1: "1",
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "10",
    20: "20",
    30: "30",
    40: "40",
    50: "50",
    60: "60",
    70: "70",
    80: "80",
    90: "90",
    100: "100",
}

# Update interval
UPDATE_INTERVAL: Final = 30  # seconds
