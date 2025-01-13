"""Constants for the IOmeter integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "iometer"
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=10)
