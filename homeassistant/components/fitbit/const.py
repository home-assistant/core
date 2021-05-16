"""Constants for the Fitbit platform."""
from __future__ import annotations

import datetime
from typing import Final

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    LENGTH_FEET,
    MASS_KILOGRAMS,
    MASS_MILLIGRAMS,
    PERCENTAGE,
    TIME_MILLISECONDS,
    TIME_MINUTES,
)

_CONFIGURING: Final[dict] = {}

ATTR_ACCESS_TOKEN: Final = "access_token"
ATTR_REFRESH_TOKEN: Final = "refresh_token"
ATTR_LAST_SAVED_AT: Final = "last_saved_at"

CONF_MONITORED_RESOURCES: Final = "monitored_resources"
CONF_CLOCK_FORMAT: Final = "clock_format"
ATTRIBUTION: Final = "Data provided by Fitbit.com"

FITBIT_AUTH_CALLBACK_PATH: Final = "/api/fitbit/callback"
FITBIT_AUTH_START: Final = "/api/fitbit"
FITBIT_CONFIG_FILE: Final = "fitbit.conf"
FITBIT_DEFAULT_RESOURCES: Final = ["activities/steps"]

SCAN_INTERVAL: Final = datetime.timedelta(minutes=30)

DEFAULT_CONFIG: Final[dict[str, str]] = {
    CONF_CLIENT_ID: "CLIENT_ID_HERE",
    CONF_CLIENT_SECRET: "CLIENT_SECRET_HERE",
}
DEFAULT_CLOCK_FORMAT: Final = "24H"

FITBIT_RESOURCES_LIST: Final[dict[str, tuple[str, str | None, str | None]]] = {
    "activities/activityCalories": ("Activity Calories", "cal", "fire"),
    "activities/calories": ("Calories", "cal", "fire"),
    "activities/caloriesBMR": ("Calories BMR", "cal", "fire"),
    "activities/distance": ("Distance", "", "map-marker"),
    "activities/elevation": ("Elevation", "", "walk"),
    "activities/floors": ("Floors", "floors", "walk"),
    "activities/heart": ("Resting Heart Rate", "bpm", "heart-pulse"),
    "activities/minutesFairlyActive": ("Minutes Fairly Active", TIME_MINUTES, "walk"),
    "activities/minutesLightlyActive": ("Minutes Lightly Active", TIME_MINUTES, "walk"),
    "activities/minutesSedentary": (
        "Minutes Sedentary",
        TIME_MINUTES,
        "seat-recline-normal",
    ),
    "activities/minutesVeryActive": ("Minutes Very Active", TIME_MINUTES, "run"),
    "activities/steps": ("Steps", "steps", "walk"),
    "activities/tracker/activityCalories": ("Tracker Activity Calories", "cal", "fire"),
    "activities/tracker/calories": ("Tracker Calories", "cal", "fire"),
    "activities/tracker/distance": ("Tracker Distance", "", "map-marker"),
    "activities/tracker/elevation": ("Tracker Elevation", "", "walk"),
    "activities/tracker/floors": ("Tracker Floors", "floors", "walk"),
    "activities/tracker/minutesFairlyActive": (
        "Tracker Minutes Fairly Active",
        TIME_MINUTES,
        "walk",
    ),
    "activities/tracker/minutesLightlyActive": (
        "Tracker Minutes Lightly Active",
        TIME_MINUTES,
        "walk",
    ),
    "activities/tracker/minutesSedentary": (
        "Tracker Minutes Sedentary",
        TIME_MINUTES,
        "seat-recline-normal",
    ),
    "activities/tracker/minutesVeryActive": (
        "Tracker Minutes Very Active",
        TIME_MINUTES,
        "run",
    ),
    "activities/tracker/steps": ("Tracker Steps", "steps", "walk"),
    "body/bmi": ("BMI", "BMI", "human"),
    "body/fat": ("Body Fat", PERCENTAGE, "human"),
    "body/weight": ("Weight", "", "human"),
    "devices/battery": ("Battery", None, None),
    "sleep/awakeningsCount": ("Awakenings Count", "times awaken", "sleep"),
    "sleep/efficiency": ("Sleep Efficiency", PERCENTAGE, "sleep"),
    "sleep/minutesAfterWakeup": ("Minutes After Wakeup", TIME_MINUTES, "sleep"),
    "sleep/minutesAsleep": ("Sleep Minutes Asleep", TIME_MINUTES, "sleep"),
    "sleep/minutesAwake": ("Sleep Minutes Awake", TIME_MINUTES, "sleep"),
    "sleep/minutesToFallAsleep": (
        "Sleep Minutes to Fall Asleep",
        TIME_MINUTES,
        "sleep",
    ),
    "sleep/startTime": ("Sleep Start Time", None, "clock"),
    "sleep/timeInBed": ("Sleep Time in Bed", TIME_MINUTES, "hotel"),
}

FITBIT_MEASUREMENTS: Final[dict[str, dict[str, str]]] = {
    "en_US": {
        "duration": TIME_MILLISECONDS,
        "distance": "mi",
        "elevation": LENGTH_FEET,
        "height": "in",
        "weight": "lbs",
        "body": "in",
        "liquids": "fl. oz.",
        "blood glucose": f"{MASS_MILLIGRAMS}/dL",
        "battery": "",
    },
    "en_GB": {
        "duration": TIME_MILLISECONDS,
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": "stone",
        "body": "centimeters",
        "liquids": "milliliters",
        "blood glucose": "mmol/L",
        "battery": "",
    },
    "metric": {
        "duration": TIME_MILLISECONDS,
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": MASS_KILOGRAMS,
        "body": "centimeters",
        "liquids": "milliliters",
        "blood glucose": "mmol/L",
        "battery": "",
    },
}

BATTERY_LEVELS: Final[dict[str, int]] = {
    "High": 100,
    "Medium": 50,
    "Low": 20,
    "Empty": 0,
}
