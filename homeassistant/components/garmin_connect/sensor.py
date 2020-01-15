"""
Platform for Garmin Connect integration.
"""
from datetime import date
from datetime import timedelta
import logging
import voluptuous as vol

import garminconnect

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_EMAIL,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    ATTR_ATTRIBUTION,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

GARMIN_RESOURCES_LIST = {
    "totalSteps": ["Total Steps", "steps", "mdi:walk"],
    "dailyStepGoal": ["Daily Step Goal", "steps", "mdi:walk"],
    "totalKilocalories": ["Total KiloCalories", "kcal", "mdi:food"],
    "activeKilocalories": ["Active KiloCalories", "kcal", "mdi:food"],
    "bmrKilocalories": ["BMR KiloCalories", "kcal", "mdi:food"],
    "consumedKilocalories": ["Consumed KiloCalories", "kcal", "mdi:food"],
    "burnedKilocalories": ["Burned KiloCalories", "kcal", "mdi:food"],
    "remainingKilocalories": ["Remaining KiloCalories", "kcal", "mdi:food"],
    "netRemainingKilocalories": ["Net Remaining KiloCalories", "kcal", "mdi:food"],
    "netCalorieGoal": ["Net Calorie Goal", "cal", "mdi:food"],
    "totalDistanceMeters": ["Total Distance Mtr", "mtr", "mdi:walk"],
    "wellnessStartTimeLocal": ["Wellness Start Time", "", "mdi:clock"],
    "wellnessEndTimeLocal": ["Wellness End Time", "", "mdi:clock"],
    "wellnessDescription": ["Wellness Description", "", "mdi:clock"],
    "wellnessDistanceMeters": ["Wellness Distance Mtr", "mtr", "mdi:walk"],
    "wellnessActiveKilocalories": ["Wellness Active KiloCalories", "kcal", "mdi:food"],
    "wellnessKilocalories": ["Wellness KiloCalories", "kcal", "mdi:food"],
    "highlyActiveSeconds": ["Highly Active Time", "minutes", "mdi:fire"],
    "activeSeconds": ["Active Time", "minutes", "mdi:fire"],
    "sedentarySeconds": ["Sedentary Time", "minutes", "mdi:seat"],
    "sleepingSeconds": ["Sleeping Time", "minutes", "mdi:sleep"],
    "measurableAwakeDuration": ["Awake Duration", "minutes", "mdi:sleep"],
    "measurableAsleepDuration": ["Sleep Duration", "minutes", "mdi:sleep"],
    "floorsAscendedInMeters": ["Floors Ascended Mtr", "mtr", "mdi:stairs"],
    "floorsDescendedInMeters": ["Floors Descended Mtr", "mtr", "mdi:stairs"],
    "floorsAscended": ["Floors Ascended", "floors", "mdi:stairs"],
    "floorsDescended": ["Floors Descended", "floors", "mdi:stairs"],
    "userFloorsAscendedGoal": ["Floors Ascended Goal", "", "mdi:stairs"],
    "minHeartRate": ["Min Heart Rate", "bpm", "mdi:heart-pulse"],
    "maxHeartRate": ["Max Heart Rate", "bpm", "mdi:heart-pulse"],
    "restingHeartRate": ["Resting Heart Rate", "bpm", "mdi:heart-pulse"],
    "minAvgHeartRate": ["Min Avg Heart Rate", "bpm", "mdi:heart-pulse"],
    "maxAvgHeartRate": ["Max Avg Heart Rate", "bpm", "mdi:heart-pulse"],
    "abnormalHeartRateAlertsCount": ["Abnormal HR Counts", "", "mdi:heart-pulse"],
    "lastSevenDaysAvgRestingHeartRate": [
        "Last 7 Days Avg Heart Rate",
        "bpm",
        "mdi:heart-pulse",
    ],
    "averageStressLevel": ["Avg Stress Level", "", "mdi:flash-alert"],
    "maxStressLevel": ["Max Stress Level", "", "mdi:flash-alert"],
    "stressQualifier": ["Stress Qualifier", "", "mdi:flash-alert"],
    "stressDuration": ["Stress Duration", "minutes", "mdi:flash-alert"],
    "restStressDuration": ["Rest Stress Duration", "minutes", "mdi:flash-alert"],
    "activityStressDuration": [
        "Activity Stress Duration",
        "minutes",
        "mdi:flash-alert",
    ],
    "uncategorizedStressDuration": [
        "Uncat. Stress Duration",
        "minutes",
        "mdi:flash-alert",
    ],
    "totalStressDuration": ["Total Stress Duration", "minutes", "mdi:flash-alert"],
    "lowStressDuration": ["Low Stress Duration", "minutes", "mdi:flash-alert"],
    "mediumStressDuration": ["Medium Stress Duration", "minutes", "mdi:flash-alert"],
    "highStressDuration": ["High Stress Duration", "minutes", "mdi:flash-alert"],
    "stressPercentage": ["Stress Percentage", "%", "mdi:flash-alert"],
    "restStressPercentage": ["Rest Stress Percentage", "%", "mdi:flash-alert"],
    "activityStressPercentage": ["Activity Stress Percentage", "%", "mdi:flash-alert"],
    "uncategorizedStressPercentage": [
        "Uncat. Stress Percentage",
        "%",
        "mdi:flash-alert",
    ],
    "lowStressPercentage": ["Low Stress Percentage", "%", "mdi:flash-alert"],
    "mediumStressPercentage": ["Medium Stress Percentage", "%", "mdi:flash-alert"],
    "highStressPercentage": ["High Stress Percentage", "%", "mdi:flash-alert"],
    "moderateIntensityMinutes": ["Moderate Intensity", "minutes", "mdi:flash-alert"],
    "vigorousIntensityMinutes": ["Vigorous Intensity", "minutes", "mdi:run-fast"],
    "intensityMinutesGoal": ["Intensity Goal", "minutes", "mdi:run-fast"],
    "bodyBatteryChargedValue": [
        "Body Battery Charged",
        "%",
        "mdi:battery-charging-100",
    ],
    "bodyBatteryDrainedValue": [
        "Body Battery Drained",
        "%",
        "mdi:battery-alert-variant-outline",
    ],
    "bodyBatteryHighestValue": ["Body Battery Highest", "%", "mdi:battery-heart"],
    "bodyBatteryLowestValue": ["Body Battery Lowest", "%", "mdi:battery-heart-outline"],
    "bodyBatteryMostRecentValue": [
        "Body Battery Most Recent",
        "%",
        "mdi:battery-positive",
    ],
    "averageSpo2": ["Average SPO2", "%", "mdi:diabetes"],
    "lowestSpo2": ["Lowest SPO2", "%", "mdi:diabetes"],
    "latestSpo2": ["Latest SPO2", "%", "mdi:diabetes"],
    "latestSpo2ReadingTimeLocal": ["Latest SPO2 Time", "", "mdi:diabetes"],
    "averageMonitoringEnvironmentAltitude": [
        "Average Altitude",
        "%",
        "mdi:image-filter-hdr",
    ],
    "durationInMilliseconds": ["Duration", "ms", "mdi:progress-clock"],
    "highestRespirationValue": ["Highest Respiration", "brpm", "mdi:progress-clock"],
    "lowestRespirationValue": ["Lowest Respiration", "brpm", "mdi:progress-clock"],
    "latestRespirationValue": ["Latest Respiration", "brpm", "mdi:progress-clock"],
    "latestRespirationTimeGMT": ["Latest Respiration Update", "", "mdi:progress-clock"],
}

_LOGGER = logging.getLogger(__name__)

GARMIN_DEFAULT_RESOURCES = ["totalSteps"]
ATTRIBUTION = "Data provided by garmin.com"
DEFAULT_NAME = "Garmin"
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=GARMIN_DEFAULT_RESOURCES
        ): vol.All(cv.ensure_list, [vol.In(GARMIN_RESOURCES_LIST)]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Garmin Connect component."""

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    prefix_name = config.get(CONF_NAME)

    try:
        garmin_client = garminconnect.Garmin(email, password)
    except ValueError as err:
        _LOGGER.error("Error occured during Garmin Connect Client init: %s", err)
        return

    garmin_data = GarminConnectClient(garmin_client)

    entities = []
    for resource in config[CONF_MONITORED_CONDITIONS]:
        sensor_type = resource
        name = prefix_name + " " + GARMIN_RESOURCES_LIST[resource][0]
        unit = GARMIN_RESOURCES_LIST[resource][1]
        icon = GARMIN_RESOURCES_LIST[resource][2]

        _LOGGER.debug(
            "Registered new sensor: %s, %s, %s, %s", sensor_type, name, unit, icon
        )
        entities.append(GarminConnectSensor(garmin_data, sensor_type, name, unit, icon))

    add_entities(entities, True)


class GarminConnectClient:
    """Set up the Garmin Connect client."""

    def __init__(self, client):
        """Initialize the client."""
        self.client = client
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch the latest data."""
        today = date.today()
        try:
            self.data = self.client.fetch_stats(today.strftime("%Y-%m-%d"))
        except ValueError as err:
            _LOGGER.error("Error occured while fetching Garmin Connect data: %s", err)
            return


class GarminConnectSensor(Entity):
    """Representation of a Garmin Connect Sensor."""

    def __init__(self, data, sensor_type, name, unit, icon):
        """Initialize the sensor."""
        self._data = data
        self._type = sensor_type
        self._name = name
        self._icon = icon
        self._unit = unit
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return attributes for sensor."""

        attributes = {}
        if self._data.data:
            attributes = {
                "source": self._data.data["source"],
                "last synced (GMT)": self._data.data["lastSyncTimestampGMT"],
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }
        return attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update data and set sensor states."""
        self._data.update()
        data = self._data.data

        if GARMIN_RESOURCES_LIST[self._type] and self._type in data:
            if "Duration" in self._type:
                self._state = data[self._type] // 60
            elif "Seconds" in self._type:
                self._state = data[self._type] // 60
            else:
                self._state = data[self._type]

       _LOGGER.debug(
            "Device %s set to state %s %s", self._type, self._state, self._unit
        )
