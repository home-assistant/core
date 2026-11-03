"""Constants for the Atomberg integration."""

from datetime import timedelta
import logging

DOMAIN = "atomberg"
LOGGER = logging.getLogger(__package__)

CONF_REFRESH_TOKEN = "refresh_token"

# The public API allows 100 calls per day; 48 polls leaves room for commands.
UPDATE_INTERVAL = timedelta(minutes=30)

FAN_SPEEDS = [1, 2, 3, 4, 5, 6]

LED_BRIGHTNESS_RANGE = (10, 100)
LIGHT_MODES = ["daylight", "cool", "warm"]

TIMER_OPTIONS = ["off", "1_hour", "2_hours", "3_hours", "6_hours"]
TIMER_HOURS = [0, 1, 2, 3, 6]

WATER_PURIFIER_MODES = {
    0: "ro_only",
    1: "adaptive",
    2: "tastetune_50_100",
    3: "tastetune_75_125",
    4: "tastetune_100_150",
    10: "vacation",
}
WATER_PURIFIER_FALLBACK_MODES = {key: WATER_PURIFIER_MODES[key] for key in (0, 2, 3, 4)}
TDS_THRESHOLD_RANGE = (100, 300)

LOCK_SERIES_TIMED_PIN = "smart_lock_black"
LOCK_GUEST_PIN_VALIDITY = timedelta(hours=4)
