"""Constants for the Garmin Connect integration."""
from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from homeassistant.const import (
    DEVICE_CLASS_TIMESTAMP,
    LENGTH_METERS,
    MASS_KILOGRAMS,
    PERCENTAGE,
    TIME_MINUTES,
)

DOMAIN = "garmin_connect"
ATTRIBUTION = "connect.garmin.com"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=10)


class GarminConnectSensorMetadata(NamedTuple):
    """Metadata for an individual Garmin Connect sensor."""

    name: str
    unit_of_measurement: str | None
    icon: str
    device_class: str | None = None
    enabled_by_default: bool = True


GARMIN_ENTITY_LIST: dict[str, GarminConnectSensorMetadata] = {
    "totalSteps": GarminConnectSensorMetadata(
        "Total Steps",
        unit_of_measurement="steps",
        icon="mdi:walk",
    ),
    "dailyStepGoal": GarminConnectSensorMetadata(
        "Daily Step Goal",
        unit_of_measurement="steps",
        icon="mdi:walk",
    ),
    "totalKilocalories": GarminConnectSensorMetadata(
        "Total KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
    ),
    "activeKilocalories": GarminConnectSensorMetadata(
        "Active KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
    ),
    "bmrKilocalories": GarminConnectSensorMetadata(
        "BMR KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
    ),
    "consumedKilocalories": GarminConnectSensorMetadata(
        "Consumed KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "burnedKilocalories": GarminConnectSensorMetadata(
        "Burned KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
    ),
    "remainingKilocalories": GarminConnectSensorMetadata(
        "Remaining KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "netRemainingKilocalories": GarminConnectSensorMetadata(
        "Net Remaining KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "netCalorieGoal": GarminConnectSensorMetadata(
        "Net Calorie Goal",
        unit_of_measurement="cal",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "totalDistanceMeters": GarminConnectSensorMetadata(
        "Total Distance Mtr",
        unit_of_measurement=LENGTH_METERS,
        icon="mdi:walk",
    ),
    "wellnessStartTimeLocal": GarminConnectSensorMetadata(
        "Wellness Start Time",
        unit_of_measurement=None,
        icon="mdi:clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
        enabled_by_default=False,
    ),
    "wellnessEndTimeLocal": GarminConnectSensorMetadata(
        "Wellness End Time",
        unit_of_measurement=None,
        icon="mdi:clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
        enabled_by_default=False,
    ),
    "wellnessDescription": GarminConnectSensorMetadata(
        "Wellness Description",
        unit_of_measurement="",
        icon="mdi:clock",
        enabled_by_default=False,
    ),
    "wellnessDistanceMeters": GarminConnectSensorMetadata(
        "Wellness Distance Mtr",
        unit_of_measurement=LENGTH_METERS,
        icon="mdi:walk",
        enabled_by_default=False,
    ),
    "wellnessActiveKilocalories": GarminConnectSensorMetadata(
        "Wellness Active KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "wellnessKilocalories": GarminConnectSensorMetadata(
        "Wellness KiloCalories",
        unit_of_measurement="kcal",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "highlyActiveSeconds": GarminConnectSensorMetadata(
        "Highly Active Time",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:fire",
        enabled_by_default=False,
    ),
    "activeSeconds": GarminConnectSensorMetadata(
        "Active Time",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:fire",
    ),
    "sedentarySeconds": GarminConnectSensorMetadata(
        "Sedentary Time",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:seat",
    ),
    "sleepingSeconds": GarminConnectSensorMetadata(
        "Sleeping Time",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:sleep",
    ),
    "measurableAwakeDuration": GarminConnectSensorMetadata(
        "Awake Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:sleep",
    ),
    "measurableAsleepDuration": GarminConnectSensorMetadata(
        "Sleep Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:sleep",
    ),
    "floorsAscendedInMeters": GarminConnectSensorMetadata(
        "Floors Ascended Mtr",
        unit_of_measurement=LENGTH_METERS,
        icon="mdi:stairs",
        enabled_by_default=False,
    ),
    "floorsDescendedInMeters": GarminConnectSensorMetadata(
        "Floors Descended Mtr",
        unit_of_measurement=LENGTH_METERS,
        icon="mdi:stairs",
        enabled_by_default=False,
    ),
    "floorsAscended": GarminConnectSensorMetadata(
        "Floors Ascended",
        unit_of_measurement="floors",
        icon="mdi:stairs",
    ),
    "floorsDescended": GarminConnectSensorMetadata(
        "Floors Descended",
        unit_of_measurement="floors",
        icon="mdi:stairs",
    ),
    "userFloorsAscendedGoal": GarminConnectSensorMetadata(
        "Floors Ascended Goal",
        unit_of_measurement="floors",
        icon="mdi:stairs",
    ),
    "minHeartRate": GarminConnectSensorMetadata(
        "Min Heart Rate",
        unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    "maxHeartRate": GarminConnectSensorMetadata(
        "Max Heart Rate",
        unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    "restingHeartRate": GarminConnectSensorMetadata(
        "Resting Heart Rate",
        unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    "minAvgHeartRate": GarminConnectSensorMetadata(
        "Min Avg Heart Rate",
        unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
        enabled_by_default=False,
    ),
    "maxAvgHeartRate": GarminConnectSensorMetadata(
        "Max Avg Heart Rate",
        unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
        enabled_by_default=False,
    ),
    "abnormalHeartRateAlertsCount": GarminConnectSensorMetadata(
        "Abnormal HR Counts",
        unit_of_measurement="",
        icon="mdi:heart-pulse",
        enabled_by_default=False,
    ),
    "lastSevenDaysAvgRestingHeartRate": GarminConnectSensorMetadata(
        "Last 7 Days Avg Heart Rate",
        unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
        enabled_by_default=False,
    ),
    "averageStressLevel": GarminConnectSensorMetadata(
        "Avg Stress Level",
        unit_of_measurement="",
        icon="mdi:flash-alert",
    ),
    "maxStressLevel": GarminConnectSensorMetadata(
        "Max Stress Level",
        unit_of_measurement="",
        icon="mdi:flash-alert",
    ),
    "stressQualifier": GarminConnectSensorMetadata(
        "Stress Qualifier",
        unit_of_measurement="",
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "stressDuration": GarminConnectSensorMetadata(
        "Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "restStressDuration": GarminConnectSensorMetadata(
        "Rest Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
    ),
    "activityStressDuration": GarminConnectSensorMetadata(
        "Activity Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
    ),
    "uncategorizedStressDuration": GarminConnectSensorMetadata(
        "Uncat. Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
    ),
    "totalStressDuration": GarminConnectSensorMetadata(
        "Total Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
    ),
    "lowStressDuration": GarminConnectSensorMetadata(
        "Low Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
    ),
    "mediumStressDuration": GarminConnectSensorMetadata(
        "Medium Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
    ),
    "highStressDuration": GarminConnectSensorMetadata(
        "High Stress Duration",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
    ),
    "stressPercentage": GarminConnectSensorMetadata(
        "Stress Percentage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "restStressPercentage": GarminConnectSensorMetadata(
        "Rest Stress Percentage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "activityStressPercentage": GarminConnectSensorMetadata(
        "Activity Stress Percentage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "uncategorizedStressPercentage": GarminConnectSensorMetadata(
        "Uncat. Stress Percentage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "lowStressPercentage": GarminConnectSensorMetadata(
        "Low Stress Percentage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "mediumStressPercentage": GarminConnectSensorMetadata(
        "Medium Stress Percentage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "highStressPercentage": GarminConnectSensorMetadata(
        "High Stress Percentage",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "moderateIntensityMinutes": GarminConnectSensorMetadata(
        "Moderate Intensity",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    "vigorousIntensityMinutes": GarminConnectSensorMetadata(
        "Vigorous Intensity",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:run-fast",
        enabled_by_default=False,
    ),
    "intensityMinutesGoal": GarminConnectSensorMetadata(
        "Intensity Goal",
        unit_of_measurement=TIME_MINUTES,
        icon="mdi:run-fast",
        enabled_by_default=False,
    ),
    "bodyBatteryChargedValue": GarminConnectSensorMetadata(
        "Body Battery Charged",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-charging-100",
    ),
    "bodyBatteryDrainedValue": GarminConnectSensorMetadata(
        "Body Battery Drained",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert-variant-outline",
    ),
    "bodyBatteryHighestValue": GarminConnectSensorMetadata(
        "Body Battery Highest",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-heart",
    ),
    "bodyBatteryLowestValue": GarminConnectSensorMetadata(
        "Body Battery Lowest",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-heart-outline",
    ),
    "bodyBatteryMostRecentValue": GarminConnectSensorMetadata(
        "Body Battery Most Recent",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-positive",
    ),
    "averageSpo2": GarminConnectSensorMetadata(
        "Average SPO2",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    "lowestSpo2": GarminConnectSensorMetadata(
        "Lowest SPO2",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    "latestSpo2": GarminConnectSensorMetadata(
        "Latest SPO2",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    "latestSpo2ReadingTimeLocal": GarminConnectSensorMetadata(
        "Latest SPO2 Time",
        unit_of_measurement=None,
        icon="mdi:diabetes",
        device_class=DEVICE_CLASS_TIMESTAMP,
        enabled_by_default=False,
    ),
    "averageMonitoringEnvironmentAltitude": GarminConnectSensorMetadata(
        "Average Altitude",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:image-filter-hdr",
        enabled_by_default=False,
    ),
    "highestRespirationValue": GarminConnectSensorMetadata(
        "Highest Respiration",
        unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        enabled_by_default=False,
    ),
    "lowestRespirationValue": GarminConnectSensorMetadata(
        "Lowest Respiration",
        unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        enabled_by_default=False,
    ),
    "latestRespirationValue": GarminConnectSensorMetadata(
        "Latest Respiration",
        unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        enabled_by_default=False,
    ),
    "latestRespirationTimeGMT": GarminConnectSensorMetadata(
        "Latest Respiration Update",
        unit_of_measurement=None,
        icon="mdi:progress-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
        enabled_by_default=False,
    ),
    "weight": GarminConnectSensorMetadata(
        "Weight",
        unit_of_measurement=MASS_KILOGRAMS,
        icon="mdi:weight-kilogram",
        enabled_by_default=False,
    ),
    "bmi": GarminConnectSensorMetadata(
        "BMI",
        unit_of_measurement="",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "bodyFat": GarminConnectSensorMetadata(
        "Body Fat",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "bodyWater": GarminConnectSensorMetadata(
        "Body Water",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        enabled_by_default=False,
    ),
    "bodyMass": GarminConnectSensorMetadata(
        "Body Mass",
        unit_of_measurement=MASS_KILOGRAMS,
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "muscleMass": GarminConnectSensorMetadata(
        "Muscle Mass",
        unit_of_measurement=MASS_KILOGRAMS,
        icon="mdi:dumbbell",
        enabled_by_default=False,
    ),
    "physiqueRating": GarminConnectSensorMetadata(
        "Physique Rating",
        unit_of_measurement="",
        icon="mdi:numeric",
        enabled_by_default=False,
    ),
    "visceralFat": GarminConnectSensorMetadata(
        "Visceral Fat",
        unit_of_measurement="",
        icon="mdi:food",
        enabled_by_default=False,
    ),
    "metabolicAge": GarminConnectSensorMetadata(
        "Metabolic Age",
        unit_of_measurement="",
        icon="mdi:calendar-heart",
        enabled_by_default=False,
    ),
    "nextAlarm": GarminConnectSensorMetadata(
        "Next Alarm Time",
        unit_of_measurement=None,
        icon="mdi:alarm",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
}
