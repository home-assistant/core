"""Constants for the WaterFurnace integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "waterfurnace"
INTEGRATION_TITLE: Final = "WaterFurnace"
UPDATE_INTERVAL: Final = timedelta(seconds=10)
ENERGY_UPDATE_INTERVAL: Final = timedelta(hours=2)
