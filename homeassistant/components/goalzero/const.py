"""Constants for the Goal Zero Yeti integration."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_POWER,
)

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
    "v12PortStatus": "12V Port Status",
    "usbPortStatus": "USB Port Status",
    "acPortStatus": "AC Port Status",
}
