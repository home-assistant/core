"""Constants for the liebherr integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "liebherr"
MANUFACTURER: Final = "Liebherr"

SCAN_INTERVAL: Final = timedelta(seconds=60)
DEVICE_SCAN_INTERVAL: Final = timedelta(minutes=5)
REFRESH_DELAY: Final = timedelta(seconds=5)
