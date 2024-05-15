"""Sensors flow for Withings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from aiowithings import (
    Activity,
    Goals,
    MeasurementType,
    SleepSummary,
    Workout,
    WorkoutCategory,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    Platform,
    UnitOfLength,
    UnitOfMass,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import WithingsConfigEntry
from .const import (
    DOMAIN,
    LOGGER,
    SCORE_POINTS,
    UOM_BEATS_PER_MINUTE,
    UOM_BREATHS_PER_MINUTE,
    UOM_FREQUENCY,
    UOM_MMHG,
)
from .coordinator import (
    WithingsActivityDataUpdateCoordinator,
    WithingsDataUpdateCoordinator,
    WithingsGoalsDataUpdateCoordinator,
    WithingsMeasurementDataUpdateCoordinator,
    WithingsSleepDataUpdateCoordinator,
    WithingsWorkoutDataUpdateCoordinator,
)
from .entity import WithingsEntity


@dataclass(frozen=True, kw_only=True)
class WithingsMeasurementSensorEntityDescription(SensorEntityDescription):
    """Immutable class for describing withings data."""

    measurement_type: MeasurementType


MEASUREMENT_SENSORS: dict[
    MeasurementType, WithingsMeasurementSensorEntityDescription
] = {
    MeasurementType.WEIGHT: WithingsMeasurementSensorEntityDescription(
        key="weight_kg",
        measurement_type=MeasurementType.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.FAT_MASS_WEIGHT: WithingsMeasurementSensorEntityDescription(
        key="fat_mass_kg",
        measurement_type=MeasurementType.FAT_MASS_WEIGHT,
        translation_key="fat_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.FAT_FREE_MASS: WithingsMeasurementSensorEntityDescription(
        key="fat_free_mass_kg",
        measurement_type=MeasurementType.FAT_FREE_MASS,
        translation_key="fat_free_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.MUSCLE_MASS: WithingsMeasurementSensorEntityDescription(
        key="muscle_mass_kg",
        measurement_type=MeasurementType.MUSCLE_MASS,
        translation_key="muscle_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.BONE_MASS: WithingsMeasurementSensorEntityDescription(
        key="bone_mass_kg",
        measurement_type=MeasurementType.BONE_MASS,
        translation_key="bone_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.HEIGHT: WithingsMeasurementSensorEntityDescription(
        key="height_m",
        measurement_type=MeasurementType.HEIGHT,
        translation_key="height",
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    MeasurementType.TEMPERATURE: WithingsMeasurementSensorEntityDescription(
        key="temperature_c",
        measurement_type=MeasurementType.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.BODY_TEMPERATURE: WithingsMeasurementSensorEntityDescription(
        key="body_temperature_c",
        measurement_type=MeasurementType.BODY_TEMPERATURE,
        translation_key="body_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.SKIN_TEMPERATURE: WithingsMeasurementSensorEntityDescription(
        key="skin_temperature_c",
        measurement_type=MeasurementType.SKIN_TEMPERATURE,
        translation_key="skin_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.FAT_RATIO: WithingsMeasurementSensorEntityDescription(
        key="fat_ratio_pct",
        measurement_type=MeasurementType.FAT_RATIO,
        translation_key="fat_ratio",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.DIASTOLIC_BLOOD_PRESSURE: WithingsMeasurementSensorEntityDescription(
        key="diastolic_blood_pressure_mmhg",
        measurement_type=MeasurementType.DIASTOLIC_BLOOD_PRESSURE,
        translation_key="diastolic_blood_pressure",
        native_unit_of_measurement=UOM_MMHG,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.SYSTOLIC_BLOOD_PRESSURE: WithingsMeasurementSensorEntityDescription(
        key="systolic_blood_pressure_mmhg",
        measurement_type=MeasurementType.SYSTOLIC_BLOOD_PRESSURE,
        translation_key="systolic_blood_pressure",
        native_unit_of_measurement=UOM_MMHG,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.HEART_RATE: WithingsMeasurementSensorEntityDescription(
        key="heart_pulse_bpm",
        measurement_type=MeasurementType.HEART_RATE,
        translation_key="heart_pulse",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.SP02: WithingsMeasurementSensorEntityDescription(
        key="spo2_pct",
        measurement_type=MeasurementType.SP02,
        translation_key="spo2",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.HYDRATION: WithingsMeasurementSensorEntityDescription(
        key="hydration",
        measurement_type=MeasurementType.HYDRATION,
        translation_key="hydration",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    MeasurementType.PULSE_WAVE_VELOCITY: WithingsMeasurementSensorEntityDescription(
        key="pulse_wave_velocity",
        measurement_type=MeasurementType.PULSE_WAVE_VELOCITY,
        translation_key="pulse_wave_velocity",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeasurementType.VO2: WithingsMeasurementSensorEntityDescription(
        key="vo2_max",
        measurement_type=MeasurementType.VO2,
        translation_key="vo2_max",
        native_unit_of_measurement="ml/min/kg",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    MeasurementType.EXTRACELLULAR_WATER: WithingsMeasurementSensorEntityDescription(
        key="extracellular_water",
        measurement_type=MeasurementType.EXTRACELLULAR_WATER,
        translation_key="extracellular_water",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    MeasurementType.INTRACELLULAR_WATER: WithingsMeasurementSensorEntityDescription(
        key="intracellular_water",
        measurement_type=MeasurementType.INTRACELLULAR_WATER,
        translation_key="intracellular_water",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    MeasurementType.VASCULAR_AGE: WithingsMeasurementSensorEntityDescription(
        key="vascular_age",
        measurement_type=MeasurementType.VASCULAR_AGE,
        translation_key="vascular_age",
        entity_registry_enabled_default=False,
    ),
    MeasurementType.VISCERAL_FAT: WithingsMeasurementSensorEntityDescription(
        key="visceral_fat",
        measurement_type=MeasurementType.VISCERAL_FAT,
        translation_key="visceral_fat_index",
        entity_registry_enabled_default=False,
    ),
    MeasurementType.ELECTRODERMAL_ACTIVITY_FEET: WithingsMeasurementSensorEntityDescription(
        key="electrodermal_activity_feet",
        measurement_type=MeasurementType.ELECTRODERMAL_ACTIVITY_FEET,
        translation_key="electrodermal_activity_feet",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    MeasurementType.ELECTRODERMAL_ACTIVITY_LEFT_FOOT: WithingsMeasurementSensorEntityDescription(
        key="electrodermal_activity_left_foot",
        measurement_type=MeasurementType.ELECTRODERMAL_ACTIVITY_LEFT_FOOT,
        translation_key="electrodermal_activity_left_foot",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    MeasurementType.ELECTRODERMAL_ACTIVITY_RIGHT_FOOT: WithingsMeasurementSensorEntityDescription(
        key="electrodermal_activity_right_foot",
        measurement_type=MeasurementType.ELECTRODERMAL_ACTIVITY_RIGHT_FOOT,
        translation_key="electrodermal_activity_right_foot",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
}


@dataclass(frozen=True, kw_only=True)
class WithingsSleepSensorEntityDescription(SensorEntityDescription):
    """Immutable class for describing withings data."""

    value_fn: Callable[[SleepSummary], StateType]


SLEEP_SENSORS = [
    WithingsSleepSensorEntityDescription(
        key="sleep_breathing_disturbances_intensity",
        value_fn=lambda sleep_summary: sleep_summary.breathing_disturbances_intensity,
        translation_key="breathing_disturbances_intensity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_deep_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.deep_sleep_duration,
        translation_key="deep_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_tosleep_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.sleep_latency,
        translation_key="time_to_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_towakeup_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.wake_up_latency,
        translation_key="time_to_wakeup",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_heart_rate_average_bpm",
        value_fn=lambda sleep_summary: sleep_summary.average_heart_rate,
        translation_key="average_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_heart_rate_max_bpm",
        value_fn=lambda sleep_summary: sleep_summary.max_heart_rate,
        translation_key="maximum_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_heart_rate_min_bpm",
        value_fn=lambda sleep_summary: sleep_summary.min_heart_rate,
        translation_key="minimum_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_light_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.light_sleep_duration,
        translation_key="light_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_rem_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.rem_sleep_duration,
        translation_key="rem_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_respiratory_average_bpm",
        value_fn=lambda sleep_summary: sleep_summary.average_respiration_rate,
        translation_key="average_respiratory_rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_respiratory_max_bpm",
        value_fn=lambda sleep_summary: sleep_summary.max_respiration_rate,
        translation_key="maximum_respiratory_rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_respiratory_min_bpm",
        value_fn=lambda sleep_summary: sleep_summary.min_respiration_rate,
        translation_key="minimum_respiratory_rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_score",
        value_fn=lambda sleep_summary: sleep_summary.sleep_score,
        translation_key="sleep_score",
        native_unit_of_measurement=SCORE_POINTS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_snoring",
        value_fn=lambda sleep_summary: sleep_summary.snoring,
        translation_key="snoring",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_snoring_eposode_count",
        value_fn=lambda sleep_summary: sleep_summary.snoring_count,
        translation_key="snoring_episode_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_wakeup_count",
        value_fn=lambda sleep_summary: sleep_summary.wake_up_count,
        translation_key="wakeup_count",
        native_unit_of_measurement=UOM_FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_wakeup_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.total_time_awake,
        translation_key="wakeup_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]


@dataclass(frozen=True, kw_only=True)
class WithingsActivitySensorEntityDescription(SensorEntityDescription):
    """Immutable class for describing withings data."""

    value_fn: Callable[[Activity], StateType]


ACTIVITY_SENSORS = [
    WithingsActivitySensorEntityDescription(
        key="activity_steps_today",
        value_fn=lambda activity: activity.steps,
        translation_key="activity_steps_today",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_distance_today",
        value_fn=lambda activity: activity.distance,
        translation_key="activity_distance_today",
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_floors_climbed_today",
        value_fn=lambda activity: activity.elevation,
        translation_key="activity_elevation_today",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_soft_duration_today",
        value_fn=lambda activity: activity.soft_activity,
        translation_key="activity_soft_duration_today",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_moderate_duration_today",
        value_fn=lambda activity: activity.moderate_activity,
        translation_key="activity_moderate_duration_today",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_intense_duration_today",
        value_fn=lambda activity: activity.intense_activity,
        translation_key="activity_intense_duration_today",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_active_duration_today",
        value_fn=lambda activity: activity.total_time_active,
        translation_key="activity_active_duration_today",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_active_calories_burnt_today",
        value_fn=lambda activity: activity.active_calories_burnt,
        suggested_display_precision=1,
        translation_key="activity_active_calories_burnt_today",
        native_unit_of_measurement="calories",
        state_class=SensorStateClass.TOTAL,
    ),
    WithingsActivitySensorEntityDescription(
        key="activity_total_calories_burnt_today",
        value_fn=lambda activity: activity.total_calories_burnt,
        suggested_display_precision=1,
        translation_key="activity_total_calories_burnt_today",
        native_unit_of_measurement="calories",
        state_class=SensorStateClass.TOTAL,
    ),
]


STEP_GOAL = "steps"
SLEEP_GOAL = "sleep"
WEIGHT_GOAL = "weight"


@dataclass(frozen=True, kw_only=True)
class WithingsGoalsSensorEntityDescription(SensorEntityDescription):
    """Immutable class for describing withings data."""

    value_fn: Callable[[Goals], StateType]


GOALS_SENSORS: dict[str, WithingsGoalsSensorEntityDescription] = {
    STEP_GOAL: WithingsGoalsSensorEntityDescription(
        key="step_goal",
        value_fn=lambda goals: goals.steps,
        translation_key="step_goal",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SLEEP_GOAL: WithingsGoalsSensorEntityDescription(
        key="sleep_goal",
        value_fn=lambda goals: goals.sleep,
        translation_key="sleep_goal",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WEIGHT_GOAL: WithingsGoalsSensorEntityDescription(
        key="weight_goal",
        value_fn=lambda goals: goals.weight,
        translation_key="weight_goal",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


@dataclass(frozen=True, kw_only=True)
class WithingsWorkoutSensorEntityDescription(SensorEntityDescription):
    """Immutable class for describing withings data."""

    value_fn: Callable[[Workout], StateType]


_WORKOUT_CATEGORY = [
    workout_category.name.lower() for workout_category in WorkoutCategory
]


WORKOUT_SENSORS = [
    WithingsWorkoutSensorEntityDescription(
        key="workout_type",
        value_fn=lambda workout: workout.category.name.lower(),
        device_class=SensorDeviceClass.ENUM,
        translation_key="workout_type",
        options=_WORKOUT_CATEGORY,
    ),
    WithingsWorkoutSensorEntityDescription(
        key="workout_active_calories_burnt",
        value_fn=lambda workout: workout.active_calories_burnt,
        translation_key="workout_active_calories_burnt",
        suggested_display_precision=1,
        native_unit_of_measurement="calories",
    ),
    WithingsWorkoutSensorEntityDescription(
        key="workout_distance",
        value_fn=lambda workout: workout.distance,
        translation_key="workout_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
    ),
    WithingsWorkoutSensorEntityDescription(
        key="workout_floors_climbed",
        value_fn=lambda workout: workout.elevation,
        translation_key="workout_elevation",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    WithingsWorkoutSensorEntityDescription(
        key="workout_intensity",
        value_fn=lambda workout: workout.intensity,
        translation_key="workout_intensity",
    ),
    WithingsWorkoutSensorEntityDescription(
        key="workout_pause_duration",
        value_fn=lambda workout: workout.pause_duration or 0,
        translation_key="workout_pause_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    WithingsWorkoutSensorEntityDescription(
        key="workout_duration",
        value_fn=lambda workout: (
            workout.end_date - workout.start_date
        ).total_seconds(),
        translation_key="workout_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
    ),
]


def get_current_goals(goals: Goals) -> set[str]:
    """Return a list of present goals."""
    result = set()
    for goal in (STEP_GOAL, SLEEP_GOAL, WEIGHT_GOAL):
        if getattr(goals, goal):
            result.add(goal)
    return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WithingsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    ent_reg = er.async_get(hass)

    withings_data = entry.runtime_data

    measurement_coordinator = withings_data.measurement_coordinator

    entities: list[SensorEntity] = []
    entities.extend(
        WithingsMeasurementSensor(
            measurement_coordinator, MEASUREMENT_SENSORS[measurement_type]
        )
        for measurement_type in measurement_coordinator.data
        if measurement_type in MEASUREMENT_SENSORS
    )

    current_measurement_types = set(measurement_coordinator.data)

    def _async_measurement_listener() -> None:
        """Listen for new measurements and add sensors if they did not exist."""
        received_measurement_types = set(measurement_coordinator.data)
        new_measurement_types = received_measurement_types - current_measurement_types
        if new_measurement_types:
            current_measurement_types.update(new_measurement_types)
            async_add_entities(
                WithingsMeasurementSensor(
                    measurement_coordinator, MEASUREMENT_SENSORS[measurement_type]
                )
                for measurement_type in new_measurement_types
            )

    measurement_coordinator.async_add_listener(_async_measurement_listener)

    goals_coordinator = withings_data.goals_coordinator

    current_goals = get_current_goals(goals_coordinator.data)

    entities.extend(
        WithingsGoalsSensor(goals_coordinator, GOALS_SENSORS[goal])
        for goal in current_goals
    )

    def _async_goals_listener() -> None:
        """Listen for new goals and add sensors if they did not exist."""
        received_goals = get_current_goals(goals_coordinator.data)
        new_goals = received_goals - current_goals
        if new_goals:
            current_goals.update(new_goals)
            async_add_entities(
                WithingsGoalsSensor(goals_coordinator, GOALS_SENSORS[goal])
                for goal in new_goals
            )

    goals_coordinator.async_add_listener(_async_goals_listener)

    activity_coordinator = withings_data.activity_coordinator

    activity_entities_setup_before = ent_reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"withings_{entry.unique_id}_activity_steps_today"
    )

    if activity_coordinator.data is not None or activity_entities_setup_before:
        entities.extend(
            WithingsActivitySensor(activity_coordinator, attribute)
            for attribute in ACTIVITY_SENSORS
        )
    else:
        remove_activity_listener: Callable[[], None]

        def _async_add_activity_entities() -> None:
            """Add activity entities."""
            if activity_coordinator.data is not None:
                async_add_entities(
                    WithingsActivitySensor(activity_coordinator, attribute)
                    for attribute in ACTIVITY_SENSORS
                )
                remove_activity_listener()

        remove_activity_listener = activity_coordinator.async_add_listener(
            _async_add_activity_entities
        )

    sleep_coordinator = withings_data.sleep_coordinator

    sleep_entities_setup_before = ent_reg.async_get_entity_id(
        Platform.SENSOR,
        DOMAIN,
        f"withings_{entry.unique_id}_sleep_deep_duration_seconds",
    )

    if sleep_coordinator.data is not None or sleep_entities_setup_before:
        entities.extend(
            WithingsSleepSensor(sleep_coordinator, attribute)
            for attribute in SLEEP_SENSORS
        )
    else:
        remove_sleep_listener: Callable[[], None]

        def _async_add_sleep_entities() -> None:
            """Add sleep entities."""
            if sleep_coordinator.data is not None:
                async_add_entities(
                    WithingsSleepSensor(sleep_coordinator, attribute)
                    for attribute in SLEEP_SENSORS
                )
                remove_sleep_listener()

        remove_sleep_listener = sleep_coordinator.async_add_listener(
            _async_add_sleep_entities
        )

    workout_coordinator = withings_data.workout_coordinator

    workout_entities_setup_before = ent_reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"withings_{entry.unique_id}_workout_type"
    )

    if workout_coordinator.data is not None or workout_entities_setup_before:
        entities.extend(
            WithingsWorkoutSensor(workout_coordinator, attribute)
            for attribute in WORKOUT_SENSORS
        )
    else:
        remove_workout_listener: Callable[[], None]

        def _async_add_workout_entities() -> None:
            """Add workout entities."""
            if workout_coordinator.data is not None:
                async_add_entities(
                    WithingsWorkoutSensor(workout_coordinator, attribute)
                    for attribute in WORKOUT_SENSORS
                )
                remove_workout_listener()

        remove_workout_listener = workout_coordinator.async_add_listener(
            _async_add_workout_entities
        )

    if not entities:
        LOGGER.warning(
            "No data found for Withings entry %s, sensors will be added when new data is available"
        )

    async_add_entities(entities)


_T = TypeVar("_T", bound=WithingsDataUpdateCoordinator)
_ED = TypeVar("_ED", bound=SensorEntityDescription)


class WithingsSensor(WithingsEntity[_T], SensorEntity, Generic[_T, _ED]):
    """Implementation of a Withings sensor."""

    entity_description: _ED

    def __init__(
        self,
        coordinator: _T,
        entity_description: _ED,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description


class WithingsMeasurementSensor(
    WithingsSensor[
        WithingsMeasurementDataUpdateCoordinator,
        WithingsMeasurementSensorEntityDescription,
    ]
):
    """Implementation of a Withings measurement sensor."""

    @property
    def native_value(self) -> float:
        """Return the state of the entity."""
        return self.coordinator.data[self.entity_description.measurement_type]

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return (
            super().available
            and self.entity_description.measurement_type in self.coordinator.data
        )


class WithingsSleepSensor(
    WithingsSensor[
        WithingsSleepDataUpdateCoordinator,
        WithingsSleepSensorEntityDescription,
    ]
):
    """Implementation of a Withings sleep sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class WithingsGoalsSensor(
    WithingsSensor[
        WithingsGoalsDataUpdateCoordinator,
        WithingsGoalsSensorEntityDescription,
    ]
):
    """Implementation of a Withings goals sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        assert self.coordinator.data
        return self.entity_description.value_fn(self.coordinator.data)


class WithingsActivitySensor(
    WithingsSensor[
        WithingsActivityDataUpdateCoordinator,
        WithingsActivitySensorEntityDescription,
    ]
):
    """Implementation of a Withings activity sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def last_reset(self) -> datetime:
        """These values reset every day."""
        return dt_util.start_of_local_day()


class WithingsWorkoutSensor(
    WithingsSensor[
        WithingsWorkoutDataUpdateCoordinator,
        WithingsWorkoutSensorEntityDescription,
    ]
):
    """Implementation of a Withings workout sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
