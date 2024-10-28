"""Constants for the Palazzetti integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "palazzetti"
PALAZZETTI: Final = "Palazzetti"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=30)
ON_OFF_NOT_AVAILABLE = "on_off_not_available"
ERROR_INVALID_FAN_MODE = "invalid_fan_mode"
ERROR_INVALID_TARGET_TEMPERATURE = "invalid_target_temperature"
ERROR_CANNOT_CONNECT = "cannot_connect"

FAN_SILENT: Final = "silent"
FAN_HIGH: Final = "high"
FAN_AUTO: Final = "auto"
FAN_MODES: Final = [FAN_SILENT, "1", "2", "3", "4", "5", FAN_HIGH, FAN_AUTO]
