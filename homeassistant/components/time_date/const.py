"""Add constants for Time & Date integration."""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

CONF_DISPLAY_OPTIONS = "display_options"
DOMAIN: Final = "time_date"
PLATFORMS = [Platform.SENSOR]
TIME_STR_FORMAT = "%H:%M"
OPTION_TYPES = {
    "time": "Time",
    "date": "Date",
    "date_time": "Date & Time",
    "date_time_utc": "Date & Time (UTC)",
    "date_time_iso": "Date & Time (ISO)",
    "time_date": "Time & Date",
    "beat": "Internet Time",
    "time_utc": "Time (UTC)",
}
