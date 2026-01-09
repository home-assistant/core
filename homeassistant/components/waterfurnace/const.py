"""Constants for the WaterFurnace integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "waterfurnace"
INTEGRATION_TITLE: Final = "WaterFurnace"

# Update intervals
SCAN_INTERVAL: Final = timedelta(seconds=10)
ERROR_INTERVAL: Final = timedelta(seconds=300)

# Connection settings
MAX_FAILS: Final = 10
