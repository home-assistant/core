"""Constants for the Palazzetti integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "palazzetti"
PALAZZETTI: Final = "Palazzetti"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)
ON_OFF_NOT_AVAILABLE = "on_off_not_available"
FAN_MODE_OUT_OF_BOUNDS = "fan_speed_out_of_bounds"
TEMPERATURE_OUT_OF_BOUNDS = "temperature_out_of_bounds"

FAN_SILENT: Final = "SILENT"
FAN_HIGH: Final = "HIGH"
FAN_AUTO: Final = "AUTO"
FAN_MODES: Final = [FAN_SILENT, "1", "2", "3", "4", "5", FAN_HIGH, FAN_AUTO]
