"""Sensors flow for Withings."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiowithings import Goals, MeasurementType, SleepSummary

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfMass,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    GOALS_COORDINATOR,
    MEASUREMENT_COORDINATOR,
    SCORE_POINTS,
    SLEEP_COORDINATOR,
    UOM_BEATS_PER_MINUTE,
    UOM_BREATHS_PER_MINUTE,
    UOM_FREQUENCY,
    UOM_MMHG,
)
from .coordinator import (
    WithingsDataUpdateCoordinator,
    WithingsGoalsDataUpdateCoordinator,
    WithingsMeasurementDataUpdateCoordinator,
    WithingsSleepDataUpdateCoordinator,
)
from .entity import WithingsEntity


@dataclass
class WithingsMeasurementSensorEntityDescriptionMixin:
    """Mixin for describing withings data."""

    measurement_type: MeasurementType


@dataclass
class WithingsMeasurementSensorEntityDescription(
    SensorEntityDescription, WithingsMeasurementSensorEntityDescriptionMixin
):
    """Immutable class for describing withings data."""


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
        icon="mdi:bone",
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
        icon="mdi:heart-pulse",
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
        icon="mdi:water",
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
}


@dataclass
class WithingsSleepSensorEntityDescriptionMixin:
    """Mixin for describing withings data."""

    value_fn: Callable[[SleepSummary], StateType]


@dataclass
class WithingsSleepSensorEntityDescription(
    SensorEntityDescription, WithingsSleepSensorEntityDescriptionMixin
):
    """Immutable class for describing withings data."""


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
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_tosleep_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.sleep_latency,
        translation_key="time_to_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_towakeup_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.wake_up_latency,
        translation_key="time_to_wakeup",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep-off",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_heart_rate_average_bpm",
        value_fn=lambda sleep_summary: sleep_summary.average_heart_rate,
        translation_key="average_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_heart_rate_max_bpm",
        value_fn=lambda sleep_summary: sleep_summary.max_heart_rate,
        translation_key="maximum_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_heart_rate_min_bpm",
        value_fn=lambda sleep_summary: sleep_summary.min_heart_rate,
        translation_key="minimum_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_light_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.light_sleep_duration,
        translation_key="light_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_rem_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.rem_sleep_duration,
        translation_key="rem_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep",
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
        icon="mdi:medal",
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
        icon="mdi:sleep-off",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WithingsSleepSensorEntityDescription(
        key="sleep_wakeup_duration_seconds",
        value_fn=lambda sleep_summary: sleep_summary.total_time_awake,
        translation_key="wakeup_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep-off",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]


STEP_GOAL = "steps"
SLEEP_GOAL = "sleep"
WEIGHT_GOAL = "weight"


@dataclass
class WithingsGoalsSensorEntityDescriptionMixin:
    """Mixin for describing withings data."""

    value_fn: Callable[[Goals], StateType]


@dataclass
class WithingsGoalsSensorEntityDescription(
    SensorEntityDescription, WithingsGoalsSensorEntityDescriptionMixin
):
    """Immutable class for describing withings data."""


GOALS_SENSORS: dict[str, WithingsGoalsSensorEntityDescription] = {
    STEP_GOAL: WithingsGoalsSensorEntityDescription(
        key="step_goal",
        value_fn=lambda goals: goals.steps,
        icon="mdi:shoe-print",
        translation_key="step_goal",
        native_unit_of_measurement="Steps",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SLEEP_GOAL: WithingsGoalsSensorEntityDescription(
        key="sleep_goal",
        value_fn=lambda goals: goals.sleep,
        icon="mdi:bed-clock",
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


def get_current_goals(goals: Goals) -> set[str]:
    """Return a list of present goals."""
    result = set()
    for goal in (STEP_GOAL, SLEEP_GOAL, WEIGHT_GOAL):
        if getattr(goals, goal):
            result.add(goal)
    return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    measurement_coordinator: WithingsMeasurementDataUpdateCoordinator = hass.data[
        DOMAIN
    ][entry.entry_id][MEASUREMENT_COORDINATOR]

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

    goals_coordinator: WithingsGoalsDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ][GOALS_COORDINATOR]

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

    sleep_coordinator: WithingsSleepDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ][SLEEP_COORDINATOR]

    entities.extend(
        WithingsSleepSensor(sleep_coordinator, attribute) for attribute in SLEEP_SENSORS
    )
    async_add_entities(entities)


class WithingsSensor(WithingsEntity, SensorEntity):
    """Implementation of a Withings sensor."""

    def __init__(
        self,
        coordinator: WithingsDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description


class WithingsMeasurementSensor(WithingsSensor):
    """Implementation of a Withings measurement sensor."""

    coordinator: WithingsMeasurementDataUpdateCoordinator

    entity_description: WithingsMeasurementSensorEntityDescription

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


class WithingsSleepSensor(WithingsSensor):
    """Implementation of a Withings sleep sensor."""

    coordinator: WithingsSleepDataUpdateCoordinator

    entity_description: WithingsSleepSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        assert self.coordinator.data
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return super().available and self.coordinator.data is not None


class WithingsGoalsSensor(WithingsSensor):
    """Implementation of a Withings goals sensor."""

    coordinator: WithingsGoalsDataUpdateCoordinator

    entity_description: WithingsGoalsSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        assert self.coordinator.data
        return self.entity_description.value_fn(self.coordinator.data)
