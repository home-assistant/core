"""Constants for the Fitbit platform."""
from __future__ import annotations

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

ATTR_ACCESS_TOKEN: Final = "access_token"
ATTR_REFRESH_TOKEN: Final = "refresh_token"
ATTR_LAST_SAVED_AT: Final = "last_saved_at"

ATTR_DURATION: Final = "duration"
ATTR_DISTANCE: Final = "distance"
ATTR_ELEVATION: Final = "elevation"
ATTR_HEIGHT: Final = "height"
ATTR_WEIGHT: Final = "weight"
ATTR_BODY: Final = "body"
ATTR_LIQUIDS: Final = "liquids"
ATTR_BLOOD_GLUCOSE: Final = "blood glucose"
ATTR_BATTERY: Final = "battery"

CONF_MONITORED_RESOURCES: Final = "monitored_resources"
CONF_CLOCK_FORMAT: Final = "clock_format"
ATTRIBUTION: Final = "Data provided by Fitbit.com"

FITBIT_AUTH_CALLBACK_PATH: Final = "/api/fitbit/callback"
FITBIT_AUTH_START: Final = "/api/fitbit"
FITBIT_CONFIG_FILE: Final = "fitbit.conf"
FITBIT_DEFAULT_RESOURCES: Final[list[str]] = ["activities/steps"]

DEFAULT_CONFIG: Final[dict[str, str]] = {
    CONF_CLIENT_ID: "CLIENT_ID_HERE",
    CONF_CLIENT_SECRET: "CLIENT_SECRET_HERE",
}
DEFAULT_CLOCK_FORMAT: Final = "24H"

FITBIT_RESOURCES_LIST: Final[dict[str, tuple[str, str | None, str]]] = {
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
    "devices/battery": ("Battery", None, "battery"),
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
        ATTR_DURATION: TIME_MILLISECONDS,
        ATTR_DISTANCE: "mi",
        ATTR_ELEVATION: LENGTH_FEET,
        ATTR_HEIGHT: "in",
        ATTR_WEIGHT: "lbs",
        ATTR_BODY: "in",
        ATTR_LIQUIDS: "fl. oz.",
        ATTR_BLOOD_GLUCOSE: f"{MASS_MILLIGRAMS}/dL",
        ATTR_BATTERY: "",
    },
    "en_GB": {
        ATTR_DURATION: TIME_MILLISECONDS,
        ATTR_DISTANCE: "kilometers",
        ATTR_ELEVATION: "meters",
        ATTR_HEIGHT: "centimeters",
        ATTR_WEIGHT: "stone",
        ATTR_BODY: "centimeters",
        ATTR_LIQUIDS: "milliliters",
        ATTR_BLOOD_GLUCOSE: "mmol/L",
        ATTR_BATTERY: "",
    },
    "metric": {
        ATTR_DURATION: TIME_MILLISECONDS,
        ATTR_DISTANCE: "kilometers",
        ATTR_ELEVATION: "meters",
        ATTR_HEIGHT: "centimeters",
        ATTR_WEIGHT: MASS_KILOGRAMS,
        ATTR_BODY: "centimeters",
        ATTR_LIQUIDS: "milliliters",
        ATTR_BLOOD_GLUCOSE: "mmol/L",
        ATTR_BATTERY: "",
    },
}

BATTERY_LEVELS: Final[dict[str, int]] = {
    "High": 100,
    "Medium": 50,
    "Low": 20,
    "Empty": 0,
}
