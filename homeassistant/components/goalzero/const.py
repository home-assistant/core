"""Constants for the Goal Zero Yeti integration."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_POWER,
)
from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
)
from homeassistant.const import (
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
    VOLT,
)

CONF_IDENTIFIERS = "identifiers"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_version"
DATA_KEY_COORDINATOR = "coordinator"
DOMAIN = "goalzero"
DEFAULT_NAME = "Yeti"
DATA_KEY_API = "api"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

BINARY_SENSOR_DICT = {
    "backlight": ["Backlight", None, "mdi:clock-digital"],
    "app_online": [
        "App Online",
        DEVICE_CLASS_CONNECTIVITY,
        None,
    ],
    "isCharging": ["Charging", DEVICE_CLASS_BATTERY_CHARGING, None],
    "inputDetected": ["Input Detected", DEVICE_CLASS_POWER, None],
}

SENSOR_DICT = {
    "wattsIn": ["Watts In", DEVICE_CLASS_POWER, POWER_WATT, True],
    "ampsIn": ["Amps In", DEVICE_CLASS_CURRENT, ELECTRICAL_CURRENT_AMPERE, False],
    "wattsOut": ["Watts Out", DEVICE_CLASS_POWER, POWER_WATT, True],
    "ampsOut": ["Amps Out", DEVICE_CLASS_CURRENT, ELECTRICAL_CURRENT_AMPERE, False],
    "whOut": ["WH Out", DEVICE_CLASS_ENERGY, ENERGY_WATT_HOUR, False],
    "whStored": ["WH Stored", DEVICE_CLASS_ENERGY, ENERGY_WATT_HOUR, True],
    "volts": ["Volts", DEVICE_CLASS_VOLTAGE, VOLT, False],
    "socPercent": ["State of Charge Percent", DEVICE_CLASS_BATTERY, PERCENTAGE, True],
    "timeToEmptyFull": ["Time to Empty/Full", TIME_MINUTES, TIME_MINUTES, True],
    "temperature": ["Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, True],
    "wifiStrength": [
        "Wifi Strength",
        DEVICE_CLASS_SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS,
        True,
    ],
    "timestamp": ["Up Time", TIME_SECONDS, TIME_SECONDS, False],
}

SWITCH_DICT = {
    "v12PortStatus": "12V Port Status",
    "usbPortStatus": "USB Port Status",
    "acPortStatus": "AC Port Status",
}
