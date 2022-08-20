"""Constants for the Android IP Webcam integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "android_ip_webcam"
DEFAULT_NAME: Final = "IP Webcam"
DEFAULT_PORT: Final = 8080
DEFAULT_TIMEOUT: Final = 10

CONF_MOTION_SENSOR: Final = "motion_sensor"

MOTION_ACTIVE: Final = "motion_active"
SCAN_INTERVAL: Final = timedelta(seconds=10)


SWITCHES = [
    "exposure_lock",
    "ffc",
    "focus",
    "gps_active",
    "motion_detect",
    "night_vision",
    "overlay",
    "torch",
    "whitebalance_lock",
    "video_recording",
]

SENSORS = [
    "audio_connections",
    "battery_level",
    "battery_temp",
    "battery_voltage",
    "light",
    "motion",
    "pressure",
    "proximity",
    "sound",
    "video_connections",
]
