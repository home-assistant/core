"""Sensors flow for Withings."""
from __future__ import annotations

from dataclasses import dataclass

from withings_api.common import GetSleepSummaryField, MeasureType

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

from .common import (
    BaseWithingsSensor,
    UpdateType,
    WithingsEntityDescription,
    async_get_data_manager,
)
from .const import (
    SCORE_POINTS,
    UOM_BEATS_PER_MINUTE,
    UOM_BREATHS_PER_MINUTE,
    UOM_FREQUENCY,
    UOM_MMHG,
    Measurement,
)


@dataclass
class WithingsSensorEntityDescription(
    SensorEntityDescription, WithingsEntityDescription
):
    """Immutable class for describing withings binary sensor data."""


SENSORS = [
    WithingsSensorEntityDescription(
        key=Measurement.WEIGHT_KG.value,
        measurement=Measurement.WEIGHT_KG,
        measure_type=MeasureType.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.FAT_MASS_KG.value,
        measurement=Measurement.FAT_MASS_KG,
        measure_type=MeasureType.FAT_MASS_WEIGHT,
        translation_key="fat_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.FAT_FREE_MASS_KG.value,
        measurement=Measurement.FAT_FREE_MASS_KG,
        measure_type=MeasureType.FAT_FREE_MASS,
        translation_key="fat_free_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.MUSCLE_MASS_KG.value,
        measurement=Measurement.MUSCLE_MASS_KG,
        measure_type=MeasureType.MUSCLE_MASS,
        translation_key="muscle_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.BONE_MASS_KG.value,
        measurement=Measurement.BONE_MASS_KG,
        measure_type=MeasureType.BONE_MASS,
        translation_key="bone_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.HEIGHT_M.value,
        measurement=Measurement.HEIGHT_M,
        measure_type=MeasureType.HEIGHT,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.TEMP_C.value,
        measurement=Measurement.TEMP_C,
        measure_type=MeasureType.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.BODY_TEMP_C.value,
        measurement=Measurement.BODY_TEMP_C,
        measure_type=MeasureType.BODY_TEMPERATURE,
        translation_key="body_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SKIN_TEMP_C.value,
        measurement=Measurement.SKIN_TEMP_C,
        measure_type=MeasureType.SKIN_TEMPERATURE,
        translation_key="skin_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.FAT_RATIO_PCT.value,
        measurement=Measurement.FAT_RATIO_PCT,
        measure_type=MeasureType.FAT_RATIO,
        translation_key="fat_ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.DIASTOLIC_MMHG.value,
        measurement=Measurement.DIASTOLIC_MMHG,
        measure_type=MeasureType.DIASTOLIC_BLOOD_PRESSURE,
        translation_key="diastolic_blood_pressure",
        native_unit_of_measurement=UOM_MMHG,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SYSTOLIC_MMGH.value,
        measurement=Measurement.SYSTOLIC_MMGH,
        measure_type=MeasureType.SYSTOLIC_BLOOD_PRESSURE,
        translation_key="systolic_blood_pressure",
        native_unit_of_measurement=UOM_MMHG,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.HEART_PULSE_BPM.value,
        measurement=Measurement.HEART_PULSE_BPM,
        measure_type=MeasureType.HEART_RATE,
        translation_key="heart_pulse",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SPO2_PCT.value,
        measurement=Measurement.SPO2_PCT,
        measure_type=MeasureType.SP02,
        translation_key="spo2",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.HYDRATION.value,
        measurement=Measurement.HYDRATION,
        measure_type=MeasureType.HYDRATION,
        translation_key="hydration",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        icon="mdi:water",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.PWV.value,
        measurement=Measurement.PWV,
        measure_type=MeasureType.PULSE_WAVE_VELOCITY,
        translation_key="pulse_wave_velocity",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY.value,
        measurement=Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY,
        measure_type=GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY,
        translation_key="breathing_disturbances_intensity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_DEEP_DURATION_SECONDS.value,
        measurement=Measurement.SLEEP_DEEP_DURATION_SECONDS,
        measure_type=GetSleepSummaryField.DEEP_SLEEP_DURATION,
        translation_key="deep_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_TOSLEEP_DURATION_SECONDS.value,
        measurement=Measurement.SLEEP_TOSLEEP_DURATION_SECONDS,
        measure_type=GetSleepSummaryField.DURATION_TO_SLEEP,
        translation_key="time_to_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS.value,
        measurement=Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS,
        measure_type=GetSleepSummaryField.DURATION_TO_WAKEUP,
        translation_key="time_to_wakeup",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep-off",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_HEART_RATE_AVERAGE.value,
        measurement=Measurement.SLEEP_HEART_RATE_AVERAGE,
        measure_type=GetSleepSummaryField.HR_AVERAGE,
        translation_key="average_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_HEART_RATE_MAX.value,
        measurement=Measurement.SLEEP_HEART_RATE_MAX,
        measure_type=GetSleepSummaryField.HR_MAX,
        translation_key="fat_mass",
        name="Maximum heart rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_HEART_RATE_MIN.value,
        measurement=Measurement.SLEEP_HEART_RATE_MIN,
        measure_type=GetSleepSummaryField.HR_MIN,
        translation_key="maximum_heart_rate",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_LIGHT_DURATION_SECONDS.value,
        measurement=Measurement.SLEEP_LIGHT_DURATION_SECONDS,
        measure_type=GetSleepSummaryField.LIGHT_SLEEP_DURATION,
        translation_key="light_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_REM_DURATION_SECONDS.value,
        measurement=Measurement.SLEEP_REM_DURATION_SECONDS,
        measure_type=GetSleepSummaryField.REM_SLEEP_DURATION,
        translation_key="rem_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE.value,
        measurement=Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE,
        measure_type=GetSleepSummaryField.RR_AVERAGE,
        translation_key="average_respiratory_rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_RESPIRATORY_RATE_MAX.value,
        measurement=Measurement.SLEEP_RESPIRATORY_RATE_MAX,
        measure_type=GetSleepSummaryField.RR_MAX,
        translation_key="maximum_respiratory_rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_RESPIRATORY_RATE_MIN.value,
        measurement=Measurement.SLEEP_RESPIRATORY_RATE_MIN,
        measure_type=GetSleepSummaryField.RR_MIN,
        translation_key="minimum_respiratory_rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_SCORE.value,
        measurement=Measurement.SLEEP_SCORE,
        measure_type=GetSleepSummaryField.SLEEP_SCORE,
        translation_key="sleep_score",
        native_unit_of_measurement=SCORE_POINTS,
        icon="mdi:medal",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_SNORING.value,
        measurement=Measurement.SLEEP_SNORING,
        measure_type=GetSleepSummaryField.SNORING,
        translation_key="snoring",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_SNORING_EPISODE_COUNT.value,
        measurement=Measurement.SLEEP_SNORING_EPISODE_COUNT,
        measure_type=GetSleepSummaryField.SNORING_EPISODE_COUNT,
        translation_key="snoring_episode_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_WAKEUP_COUNT.value,
        measurement=Measurement.SLEEP_WAKEUP_COUNT,
        measure_type=GetSleepSummaryField.WAKEUP_COUNT,
        translation_key="wakeup_count",
        native_unit_of_measurement=UOM_FREQUENCY,
        icon="mdi:sleep-off",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_WAKEUP_DURATION_SECONDS.value,
        measurement=Measurement.SLEEP_WAKEUP_DURATION_SECONDS,
        measure_type=GetSleepSummaryField.WAKEUP_DURATION,
        translation_key="wakeup_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:sleep-off",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    data_manager = await async_get_data_manager(hass, entry)

    entities = [WithingsHealthSensor(data_manager, attribute) for attribute in SENSORS]

    async_add_entities(entities, True)


class WithingsHealthSensor(BaseWithingsSensor, SensorEntity):
    """Implementation of a Withings sensor."""

    entity_description: WithingsSensorEntityDescription

    @property
    def native_value(self) -> None | str | int | float:
        """Return the state of the entity."""
        return self._state_data
