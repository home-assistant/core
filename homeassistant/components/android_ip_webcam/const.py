"""Constants for the Android IP Webcam integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "android_ip_webcam"
DEFAULT_PORT: Final = 8080
MOTION_ACTIVE: Final = "motion_active"
SCAN_INTERVAL: Final = timedelta(seconds=10)
