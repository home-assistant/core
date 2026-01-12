"""Sensor platform for Garmin Connect."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GarminConnectConfigEntry
from .const import DOMAIN
from .coordinator import CoreCoordinator

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to prevent API rate limiting
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class GarminConnectSensorEntityDescription(SensorEntityDescription):
    """Describes Garmin Connect sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None
    """Function to extract value from coordinator data."""

    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    """Function to extract attributes from coordinator data."""

    preserve_value: bool = False
    """If True, preserve last known value when API returns None (for weight, BMI, etc)."""


# Activity & Steps Sensors
ACTIVITY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalSteps",
        translation_key="total_steps",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
        icon="mdi:walk",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="dailyStepGoal",
        translation_key="daily_step_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
        icon="mdi:target",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdaySteps",
        translation_key="yesterday_steps",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
        icon="mdi:walk",
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyStepAvg",
        translation_key="weekly_step_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="steps",
        icon="mdi:chart-line",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdayDistance",
        translation_key="yesterday_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:map-marker-distance",
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyDistanceAvg",
        translation_key="weekly_distance_avg",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:chart-line",
    ),
    GarminConnectSensorEntityDescription(
        key="totalDistanceMeters",
        translation_key="total_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:walk",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="floorsAscended",
        translation_key="floors_ascended",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
        icon="mdi:stairs-up",
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescended",
        translation_key="floors_descended",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
        icon="mdi:stairs-down",
    ),
    GarminConnectSensorEntityDescription(
        key="userFloorsAscendedGoal",
        translation_key="floors_ascended_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
        icon="mdi:target",
    ),
)

# Calories & Nutrition Sensors
CALORIES_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalKilocalories",
        translation_key="total_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="activeKilocalories",
        translation_key="active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="bmrKilocalories",
        translation_key="bmr_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire-circle",
    ),
    GarminConnectSensorEntityDescription(
        key="burnedKilocalories",
        translation_key="burned_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="consumedKilocalories",
        translation_key="consumed_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:food",
    ),
    GarminConnectSensorEntityDescription(
        key="remainingKilocalories",
        translation_key="remaining_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:food",
    ),
)

# Heart Rate Sensors
HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="restingHeartRate",
        translation_key="resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="maxHeartRate",
        translation_key="max_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="minHeartRate",
        translation_key="min_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="lastSevenDaysAvgRestingHeartRate",
        translation_key="last_7_days_avg_resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="hrvStatusText",
        translation_key="hrv_status",
        icon="mdi:heart-pulse",
        attributes_fn=lambda data: {
            k: v for k, v in data.get("hrvStatus", {}).items() if k != "status"
        }
        if data.get("hrvStatus")
        else {},
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvWeeklyAvg",
        translation_key="hrv_weekly_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvLastNightAvg",
        translation_key="hrv_last_night_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvLastNight5MinHigh",
        translation_key="hrv_last_night_5min_high",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvBaselineLowUpper",
        translation_key="hrv_baseline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        attributes_fn=lambda data: data.get("hrvStatus", {}).get("baseline", {}),
        preserve_value=True,
    ),
)

# Stress Sensors
STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageStressLevel",
        translation_key="avg_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
        icon="mdi:gauge",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="maxStressLevel",
        translation_key="max_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
        icon="mdi:gauge-full",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="stressQualifierText",
        translation_key="stress_qualifier",
        icon="mdi:emoticon",
    ),
    GarminConnectSensorEntityDescription(
        key="stressDuration",
        translation_key="total_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer",
        value_fn=lambda data: round(data.get("stressDuration", 0) / 60)
        if data.get("stressDuration")
        else None,
    ),
    GarminConnectSensorEntityDescription(
        key="restStressDuration",
        translation_key="rest_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-pause",
        value_fn=lambda data: round(data.get("restStressDuration", 0) / 60)
        if data.get("restStressDuration")
        else None,
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressDuration",
        translation_key="activity_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-play",
        value_fn=lambda data: round(data.get("activityStressDuration", 0) / 60)
        if data.get("activityStressDuration")
        else None,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressDuration",
        translation_key="low_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-check",
        value_fn=lambda data: round(data.get("lowStressDuration", 0) / 60)
        if data.get("lowStressDuration")
        else None,
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressDuration",
        translation_key="medium_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-alert",
        value_fn=lambda data: round(data.get("mediumStressDuration", 0) / 60)
        if data.get("mediumStressDuration")
        else None,
    ),
    GarminConnectSensorEntityDescription(
        key="highStressDuration",
        translation_key="high_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-remove",
        value_fn=lambda data: round(data.get("highStressDuration", 0) / 60)
        if data.get("highStressDuration")
        else None,
        preserve_value=True,
    ),
)

# Sleep Sensors
SLEEP_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="sleepingMinutes",
        translation_key="sleeping_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepTimeMinutes",
        translation_key="total_sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAsleepDurationMinutes",
        translation_key="sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAwakeDurationMinutes",
        translation_key="awake_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep-off",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepScore",
        translation_key="sleep_score",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="deepSleepMinutes",
        translation_key="deep_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="lightSleepMinutes",
        translation_key="light_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="remSleepMinutes",
        translation_key="rem_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="awakeSleepMinutes",
        translation_key="awake_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep-off",
        preserve_value=True,
    ),
)

# Body Battery Sensors
BODY_BATTERY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="bodyBatteryMostRecentValue",
        translation_key="body_battery_most_recent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-heart",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryHighestValue",
        translation_key="body_battery_highest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-charging-100",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryLowestValue",
        translation_key="body_battery_lowest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-heart-outline",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryChargedValue",
        translation_key="body_battery_charged",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-plus",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryDrainedValue",
        translation_key="body_battery_drained",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-minus",
    ),
)

# Intensity & Activity Time Sensors
INTENSITY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="activeMinutes",
        translation_key="active_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:fire",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="highlyActiveMinutes",
        translation_key="highly_active_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="sedentaryMinutes",
        translation_key="sedentary_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:seat",
    ),
    GarminConnectSensorEntityDescription(
        key="moderateIntensityMinutes",
        translation_key="moderate_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:flash-alert",
    ),
    GarminConnectSensorEntityDescription(
        key="vigorousIntensityMinutes",
        translation_key="vigorous_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:run-fast",
    ),
    GarminConnectSensorEntityDescription(
        key="intensityMinutesGoal",
        translation_key="intensity_goal",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:target",
    ),
    GarminConnectSensorEntityDescription(
        key="totalIntensityMinutes",
        translation_key="total_intensity_minutes",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:fire",
        value_fn=lambda data: (
            (data.get("moderateIntensityMinutes") or 0)
            + ((data.get("vigorousIntensityMinutes") or 0) * 2)
        )
        if data.get("moderateIntensityMinutes") is not None
        or data.get("vigorousIntensityMinutes") is not None
        else None,
        attributes_fn=lambda data: {
            "moderate_minutes": data.get("moderateIntensityMinutes"),
            "vigorous_minutes": data.get("vigorousIntensityMinutes"),
            "goal": data.get("intensityMinutesGoal"),
        },
    ),
)

# SPO2 & Respiration Sensors
HEALTH_MONITORING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageSpo2",
        translation_key="avg_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    GarminConnectSensorEntityDescription(
        key="lowestSpo2",
        translation_key="lowest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2",
        translation_key="latest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2ReadingTimeLocal",
        translation_key="latest_spo2_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
    GarminConnectSensorEntityDescription(
        key="highestRespirationValue",
        translation_key="highest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="lowestRespirationValue",
        translation_key="lowest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationValue",
        translation_key="latest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationTimeGMT",
        translation_key="latest_respiration_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
    GarminConnectSensorEntityDescription(
        key="averageMonitoringEnvironmentAltitude",
        translation_key="avg_altitude",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:image-filter-hdr",
    ),
)

# Additional Heart Rate Sensors (less common)
ADDITIONAL_HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="minAvgHeartRate",
        translation_key="min_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="maxAvgHeartRate",
        translation_key="max_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="abnormalHeartRateAlertsCount",
        translation_key="abnormal_hr_alerts",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:heart-pulse",
    ),
)

# Additional stress percentage sensors (disabled by default - less useful)
STRESS_PERCENTAGE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="stressPercentage",
        translation_key="stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
    ),
    GarminConnectSensorEntityDescription(
        key="restStressPercentage",
        translation_key="rest_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressPercentage",
        translation_key="activity_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
    ),
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressPercentage",
        translation_key="uncategorized_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressPercentage",
        translation_key="low_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressPercentage",
        translation_key="medium_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
    ),
    GarminConnectSensorEntityDescription(
        key="highStressPercentage",
        translation_key="high_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
    ),
)

# Additional stress duration sensor
ADDITIONAL_STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressDuration",
        translation_key="uncategorized_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:flash-alert",
        value_fn=lambda data: round(data.get("uncategorizedStressDuration", 0) / 60, 2)
        if data.get("uncategorizedStressDuration")
        else None,
    ),
)

# Additional distance sensors (meters variants - disabled by default)
ADDITIONAL_DISTANCE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="floorsAscendedInMeters",
        translation_key="floors_ascended_meters",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:stairs-up",
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescendedInMeters",
        translation_key="floors_descended_meters",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:stairs-down",
    ),
)

# Wellness sensors (disabled by default - typically not used)
WELLNESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="wellnessStartTimeLocal",
        translation_key="wellness_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessEndTimeLocal",
        translation_key="wellness_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDescription",
        translation_key="wellness_description",
        icon="mdi:text",
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDistanceMeters",
        translation_key="wellness_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:walk",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessActiveKilocalories",
        translation_key="wellness_active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessKilocalories",
        translation_key="wellness_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
)

# Diagnostic Sensors
DIAGNOSTIC_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="lastSyncTimestampGMT",
        translation_key="device_last_synced",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:sync",
        # Value is already an ISO timestamp string, just pass it through
        value_fn=lambda data: data.get("lastSyncTimestampGMT"),
    ),
)


# All CORE sensor descriptions
SENSOR_DESCRIPTIONS: tuple[GarminConnectSensorEntityDescription, ...] = (
    *ACTIVITY_SENSORS,
    *CALORIES_SENSORS,
    *HEART_RATE_SENSORS,
    *ADDITIONAL_HEART_RATE_SENSORS,
    *STRESS_SENSORS,
    *ADDITIONAL_STRESS_SENSORS,
    *STRESS_PERCENTAGE_SENSORS,
    *SLEEP_SENSORS,
    *BODY_BATTERY_SENSORS,
    *INTENSITY_SENSORS,
    *HEALTH_MONITORING_SENSORS,
    *ADDITIONAL_DISTANCE_SENSORS,
    *WELLNESS_SENSORS,
    *DIAGNOSTIC_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GarminConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garmin Connect sensors."""
    coordinators = entry.runtime_data
    coordinator = coordinators.core

    entities: list[GarminConnectSensor] = []

    for description in SENSOR_DESCRIPTIONS:
        _LOGGER.debug(
            "Registering entity: %s (%s)",
            description.key,
            description.translation_key,
        )
        entities.append(GarminConnectSensor(coordinator, description, entry.entry_id))

    async_add_entities(entities)


class GarminConnectSensor(CoordinatorEntity[CoreCoordinator], RestoreSensor):
    """Representation of a Garmin Connect sensor."""

    entity_description: GarminConnectSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoreCoordinator,
        description: GarminConnectSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._last_known_value: str | int | float | datetime.datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last known value when added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in ("unknown", "unavailable"):
                self._last_known_value = last_state.state

    @property
    def native_value(self) -> str | int | float | datetime.datetime | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            # Only return last known value if preserve_value is enabled
            if self.entity_description.preserve_value:
                return self._last_known_value
            return None

        # Use custom value function if provided in description
        if self.entity_description.value_fn:
            value = self.entity_description.value_fn(self.coordinator.data)
        else:
            value = self.coordinator.data.get(self.entity_description.key)

        if value is None:
            # Return last known value if preserve_value enabled (e.g., weight at midnight)
            if self.entity_description.preserve_value:
                return self._last_known_value
            return None

        # Handle timestamp device class
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if value:
                try:
                    # Parse ISO format timestamp and set to UTC (GMT)
                    parsed = datetime.datetime.fromisoformat(value)
                    # If naive, assume UTC since Garmin returns GMT timestamps
                    if parsed.tzinfo is None:
                        value = parsed.replace(tzinfo=datetime.UTC)
                    else:
                        value = parsed
                except (ValueError, TypeError):
                    _LOGGER.debug("Could not parse timestamp: %s", value)
                    value = None

        # Preserve int types, only round floats
        if isinstance(value, int):
            self._last_known_value = value
            return value
        if isinstance(value, float):
            # Round floats to 1 decimal place, but return int if it's a whole number
            rounded = round(value, 1)
            if rounded == int(rounded):
                self._last_known_value = int(rounded)
                return int(rounded)
            self._last_known_value = rounded
            return rounded
        # For strings and datetime objects, return as-is
        if isinstance(value, (str, datetime.datetime)):
            self._last_known_value = value
            return value
        # Fallback: return as string
        self._last_known_value = str(value)
        return str(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        # Use custom attributes function if provided in description
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.coordinator.data)

        # Default: no extra attributes (last_synced has its own sensor)
        return {}
