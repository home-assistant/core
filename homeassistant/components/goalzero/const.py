"""Constants for the Goal Zero Yeti integration."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_POWER,
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

SWITCH_DICT = {
    "v12PortStatus": ["12V Port Status", DEVICE_CLASS_POWER, None],
    "usbPortStatus": ["USB Port Status", DEVICE_CLASS_POWER, None],
    "acPortStatus": ["AC Port Status", DEVICE_CLASS_POWER, None],
}
