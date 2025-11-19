"""Constants for the Airobot integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "airobot"

# Update interval - thermostat measures air every 30 seconds
UPDATE_INTERVAL: Final = timedelta(seconds=30)
