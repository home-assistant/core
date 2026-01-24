"""Sensor platform for Garmin Connect."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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


# Activity & Steps Sensors
ACTIVITY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalSteps",
        translation_key="total_steps",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
    ),
    GarminConnectSensorEntityDescription(
        key="dailyStepGoal",
        translation_key="daily_step_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdaySteps",
        translation_key="yesterday_steps",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyStepAvg",
        translation_key="weekly_step_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="steps",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdayDistance",
        translation_key="yesterday_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyDistanceAvg",
        translation_key="weekly_distance_avg",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    GarminConnectSensorEntityDescription(
        key="totalDistanceMeters",
        translation_key="total_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    GarminConnectSensorEntityDescription(
        key="floorsAscended",
        translation_key="floors_ascended",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescended",
        translation_key="floors_descended",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
    ),
    GarminConnectSensorEntityDescription(
        key="userFloorsAscendedGoal",
        translation_key="floors_ascended_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
    ),
)

# Calories & Nutrition Sensors
CALORIES_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalKilocalories",
        translation_key="total_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
    GarminConnectSensorEntityDescription(
        key="activeKilocalories",
        translation_key="active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
    GarminConnectSensorEntityDescription(
        key="bmrKilocalories",
        translation_key="bmr_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
    GarminConnectSensorEntityDescription(
        key="burnedKilocalories",
        translation_key="burned_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
    GarminConnectSensorEntityDescription(
        key="consumedKilocalories",
        translation_key="consumed_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
    GarminConnectSensorEntityDescription(
        key="remainingKilocalories",
        translation_key="remaining_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
)

# Heart Rate Sensors
HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="restingHeartRate",
        translation_key="resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="maxHeartRate",
        translation_key="max_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="minHeartRate",
        translation_key="min_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="lastSevenDaysAvgRestingHeartRate",
        translation_key="last_7_days_avg_resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
)


# Stress Sensors
STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageStressLevel",
        translation_key="avg_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
    ),
    GarminConnectSensorEntityDescription(
        key="maxStressLevel",
        translation_key="max_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
    ),
    GarminConnectSensorEntityDescription(
        key="stressQualifierText",
        translation_key="stress_qualifier",
    ),
    GarminConnectSensorEntityDescription(
        key="stressMinutes",
        translation_key="total_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="restStressMinutes",
        translation_key="rest_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressMinutes",
        translation_key="activity_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressMinutes",
        translation_key="low_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressMinutes",
        translation_key="medium_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="highStressMinutes",
        translation_key="high_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
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
    ),
    GarminConnectSensorEntityDescription(
        key="sleepTimeMinutes",
        translation_key="total_sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAsleepDurationMinutes",
        translation_key="sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAwakeDurationMinutes",
        translation_key="awake_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepScore",
        translation_key="sleep_score",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GarminConnectSensorEntityDescription(
        key="deepSleepMinutes",
        translation_key="deep_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="lightSleepMinutes",
        translation_key="light_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="remSleepMinutes",
        translation_key="rem_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="awakeSleepMinutes",
        translation_key="awake_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="napTimeMinutes",
        translation_key="nap_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="unmeasurableSleepMinutes",
        translation_key="unmeasurable_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)


# Body Battery Sensors
BODY_BATTERY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="bodyBatteryMostRecentValue",
        translation_key="body_battery_most_recent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryHighestValue",
        translation_key="body_battery_highest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryLowestValue",
        translation_key="body_battery_lowest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryChargedValue",
        translation_key="body_battery_charged",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryDrainedValue",
        translation_key="body_battery_drained",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
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
    ),
    GarminConnectSensorEntityDescription(
        key="highlyActiveMinutes",
        translation_key="highly_active_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="sedentaryMinutes",
        translation_key="sedentary_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="moderateIntensityMinutes",
        translation_key="moderate_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="vigorousIntensityMinutes",
        translation_key="vigorous_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="intensityMinutesGoal",
        translation_key="intensity_goal",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="totalIntensityMinutes",
        translation_key="total_intensity_minutes",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

# SPO2 & Respiration Sensors
HEALTH_MONITORING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageSpo2",
        translation_key="avg_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="lowestSpo2",
        translation_key="lowest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2",
        translation_key="latest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2ReadingTime",
        translation_key="latest_spo2_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="highestRespirationValue",
        translation_key="highest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
    ),
    GarminConnectSensorEntityDescription(
        key="lowestRespirationValue",
        translation_key="lowest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationValue",
        translation_key="latest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationTime",
        translation_key="latest_respiration_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="averageMonitoringEnvironmentAltitude",
        translation_key="avg_altitude",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

# Additional Heart Rate Sensors (less common)
ADDITIONAL_HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="minAvgHeartRate",
        translation_key="min_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="maxAvgHeartRate",
        translation_key="max_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="abnormalHeartRateAlertsCount",
        translation_key="abnormal_hr_alerts",
        state_class=SensorStateClass.TOTAL,
    ),
)

# Additional stress percentage sensors (disabled by default - less useful)
STRESS_PERCENTAGE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="stressPercentage",
        translation_key="stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="restStressPercentage",
        translation_key="rest_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressPercentage",
        translation_key="activity_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressPercentage",
        translation_key="uncategorized_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressPercentage",
        translation_key="low_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressPercentage",
        translation_key="medium_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="highStressPercentage",
        translation_key="high_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

# Additional stress duration sensor
ADDITIONAL_STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressMinutes",
        translation_key="uncategorized_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

# Additional distance sensors (distance variants - disabled by default)
ADDITIONAL_DISTANCE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="floorsAscendedInMeters",
        translation_key="floors_ascended_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescendedInMeters",
        translation_key="floors_descended_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
)

# Wellness sensors (disabled by default - typically not used)
WELLNESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="wellnessStartTime",
        translation_key="wellness_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessEndTime",
        translation_key="wellness_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDistanceMeters",
        translation_key="wellness_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessActiveKilocalories",
        translation_key="wellness_active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessKilocalories",
        translation_key="wellness_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
    ),
)



# Sync Sensors
SYNC_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="lastSyncTimestamp",
        translation_key="last_synced",
        device_class=SensorDeviceClass.TIMESTAMP,
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
    *SYNC_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GarminConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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


class GarminConnectSensor(CoordinatorEntity[CoreCoordinator], SensorEntity):
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

    @property
    def native_value(self) -> str | int | float | datetime.datetime | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        value = self.coordinator.data.get(self.entity_description.key)

        if value is None:
            return None

        # Preserve int types, only round floats
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            # Round floats to 1 decimal place, but return int if it's a whole number
            rounded = round(value, 1)
            if rounded == int(rounded):
                return int(rounded)
            return rounded
        # For strings and datetime objects, return as-is
        if isinstance(value, (str, datetime.datetime)):
            return value
        # Fallback: return as string
        return str(value)

