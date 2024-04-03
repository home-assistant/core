"""Constants for the Time & Date integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

CONF_DISPLAY_OPTIONS = "display_options"
DOMAIN: Final = "time_date"
PLATFORMS = [Platform.SENSOR]
TIME_STR_FORMAT = "%H:%M"

OPTION_TYPES = [
    "time",
    "date",
    "date_time",
    "date_time_utc",
    "date_time_iso",
    "time_date",
    "beat",
    "time_utc",
]
