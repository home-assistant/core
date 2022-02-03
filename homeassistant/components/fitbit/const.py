"""Constants for the Fitbit platform."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import SensorEntityDescription
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


@dataclass
class FitbitRequiredKeysMixin:
    """Mixin for required keys."""

    unit_type: str | None


@dataclass
class FitbitSensorEntityDescription(SensorEntityDescription, FitbitRequiredKeysMixin):
    """Describes Fitbit sensor entity."""


FITBIT_RESOURCES_LIST: Final[tuple[FitbitSensorEntityDescription, ...]] = (
    FitbitSensorEntityDescription(
        key="activities/activityCalories",
        name="Activity Calories",
        unit_type="cal",
        icon="mdi:fire",
    ),
    FitbitSensorEntityDescription(
        key="activities/calories",
        name="Calories",
        unit_type="cal",
        icon="mdi:fire",
    ),
    FitbitSensorEntityDescription(
        key="activities/caloriesBMR",
        name="Calories BMR",
        unit_type="cal",
        icon="mdi:fire",
    ),
    FitbitSensorEntityDescription(
        key="activities/distance",
        name="Distance",
        unit_type="",
        icon="mdi:map-marker",
    ),
    FitbitSensorEntityDescription(
        key="activities/elevation",
        name="Elevation",
        unit_type="",
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/floors",
        name="Floors",
        unit_type="floors",
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/heart",
        name="Resting Heart Rate",
        unit_type="bpm",
        icon="mdi:heart-pulse",
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesFairlyActive",
        name="Minutes Fairly Active",
        unit_type=TIME_MINUTES,
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesLightlyActive",
        name="Minutes Lightly Active",
        unit_type=TIME_MINUTES,
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesSedentary",
        name="Minutes Sedentary",
        unit_type=TIME_MINUTES,
        icon="mdi:seat-recline-normal",
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesVeryActive",
        name="Minutes Very Active",
        unit_type=TIME_MINUTES,
        icon="mdi:run",
    ),
    FitbitSensorEntityDescription(
        key="activities/steps",
        name="Steps",
        unit_type="steps",
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/activityCalories",
        name="Tracker Activity Calories",
        unit_type="cal",
        icon="mdi:fire",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/calories",
        name="Tracker Calories",
        unit_type="cal",
        icon="mdi:fire",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/distance",
        name="Tracker Distance",
        unit_type="",
        icon="mdi:map-marker",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/elevation",
        name="Tracker Elevation",
        unit_type="",
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/floors",
        name="Tracker Floors",
        unit_type="floors",
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesFairlyActive",
        name="Tracker Minutes Fairly Active",
        unit_type=TIME_MINUTES,
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesLightlyActive",
        name="Tracker Minutes Lightly Active",
        unit_type=TIME_MINUTES,
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesSedentary",
        name="Tracker Minutes Sedentary",
        unit_type=TIME_MINUTES,
        icon="mdi:seat-recline-normal",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesVeryActive",
        name="Tracker Minutes Very Active",
        unit_type=TIME_MINUTES,
        icon="mdi:run",
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/steps",
        name="Tracker Steps",
        unit_type="steps",
        icon="mdi:walk",
    ),
    FitbitSensorEntityDescription(
        key="body/bmi",
        name="BMI",
        unit_type="BMI",
        icon="mdi:human",
    ),
    FitbitSensorEntityDescription(
        key="body/fat",
        name="Body Fat",
        unit_type=PERCENTAGE,
        icon="mdi:human",
    ),
    FitbitSensorEntityDescription(
        key="body/weight",
        name="Weight",
        unit_type="",
        icon="mdi:human",
    ),
    FitbitSensorEntityDescription(
        key="sleep/awakeningsCount",
        name="Awakenings Count",
        unit_type="times awaken",
        icon="mdi:sleep",
    ),
    FitbitSensorEntityDescription(
        key="sleep/efficiency",
        name="Sleep Efficiency",
        unit_type=PERCENTAGE,
        icon="mdi:sleep",
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesAfterWakeup",
        name="Minutes After Wakeup",
        unit_type=TIME_MINUTES,
        icon="mdi:sleep",
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesAsleep",
        name="Sleep Minutes Asleep",
        unit_type=TIME_MINUTES,
        icon="mdi:sleep",
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesAwake",
        name="Sleep Minutes Awake",
        unit_type=TIME_MINUTES,
        icon="mdi:sleep",
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesToFallAsleep",
        name="Sleep Minutes to Fall Asleep",
        unit_type=TIME_MINUTES,
        icon="mdi:sleep",
    ),
    FitbitSensorEntityDescription(
        key="sleep/startTime",
        name="Sleep Start Time",
        unit_type=None,
        icon="mdi:clock",
    ),
    FitbitSensorEntityDescription(
        key="sleep/timeInBed",
        name="Sleep Time in Bed",
        unit_type=TIME_MINUTES,
        icon="mdi:hotel",
    ),
)

FITBIT_RESOURCE_BATTERY = FitbitSensorEntityDescription(
    key="devices/battery",
    name="Battery",
    unit_type=None,
    icon="mdi:battery",
)

FITBIT_RESOURCES_KEYS: Final[list[str]] = [
    desc.key for desc in (*FITBIT_RESOURCES_LIST, FITBIT_RESOURCE_BATTERY)
]

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
