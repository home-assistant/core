"""The Proximity constants."""
DOMAIN = "time_date"
CONF_OPTIONS = "display_options"
DISPLAY_OPTIONS = [
    "time",
    "date",
    "date_time",
    "date_time_utc",
    "date_time_iso",
    "time_date",
    "time_utc",
    "beat",
]

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
