"""Constants for Nextcloud integration."""
from datetime import timedelta

DOMAIN = "nextcloud"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_VERIFY_SSL = True

IGNORE_SENSORS = (
    "system apps app_updates",
    "system update available_version",
    "system version",
)

BOOLEAN_TRUE_VALUES = ["yes"]
BOOLEN_VALUES = BOOLEAN_TRUE_VALUES + ["no"]
