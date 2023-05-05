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
        name="Weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.FAT_MASS_KG.value,
        measurement=Measurement.FAT_MASS_KG,
        measure_type=MeasureType.FAT_MASS_WEIGHT,
        name="Fat Mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.FAT_FREE_MASS_KG.value,
        measurement=Measurement.FAT_FREE_MASS_KG,
        measure_type=MeasureType.FAT_FREE_MASS,
        name="Fat Free Mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.MUSCLE_MASS_KG.value,
        measurement=Measurement.MUSCLE_MASS_KG,
        measure_type=MeasureType.MUSCLE_MASS,
        name="Muscle Mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.BONE_MASS_KG.value,
        measurement=Measurement.BONE_MASS_KG,
        measure_type=MeasureType.BONE_MASS,
        name="Bone Mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.HEIGHT_M.value,
        measurement=Measurement.HEIGHT_M,
        measure_type=MeasureType.HEIGHT,
        name="Height",
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
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.BODY_TEMP_C.value,
        measurement=Measurement.BODY_TEMP_C,
        measure_type=MeasureType.BODY_TEMPERATURE,
        name="Body Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SKIN_TEMP_C.value,
        measurement=Measurement.SKIN_TEMP_C,
        measure_type=MeasureType.SKIN_TEMPERATURE,
        name="Skin Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.FAT_RATIO_PCT.value,
        measurement=Measurement.FAT_RATIO_PCT,
        measure_type=MeasureType.FAT_RATIO,
        name="Fat Ratio",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.DIASTOLIC_MMHG.value,
        measurement=Measurement.DIASTOLIC_MMHG,
        measure_type=MeasureType.DIASTOLIC_BLOOD_PRESSURE,
        name="Diastolic Blood Pressure",
        native_unit_of_measurement=UOM_MMHG,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SYSTOLIC_MMGH.value,
        measurement=Measurement.SYSTOLIC_MMGH,
        measure_type=MeasureType.SYSTOLIC_BLOOD_PRESSURE,
        name="Systolic Blood Pressure",
        native_unit_of_measurement=UOM_MMHG,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.HEART_PULSE_BPM.value,
        measurement=Measurement.HEART_PULSE_BPM,
        measure_type=MeasureType.HEART_RATE,
        name="Heart Pulse",
        native_unit_of_measurement=UOM_BEATS_PER_MINUTE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SPO2_PCT.value,
        measurement=Measurement.SPO2_PCT,
        measure_type=MeasureType.SP02,
        name="SP02",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.HYDRATION.value,
        measurement=Measurement.HYDRATION,
        measure_type=MeasureType.HYDRATION,
        name="Hydration",
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
        name="Pulse Wave Velocity",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY.value,
        measurement=Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY,
        measure_type=GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY,
        name="Breathing disturbances intensity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_DEEP_DURATION_SECONDS.value,
        measurement=Measurement.SLEEP_DEEP_DURATION_SECONDS,
        measure_type=GetSleepSummaryField.DEEP_SLEEP_DURATION,
        name="Deep sleep",
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
        name="Time to sleep",
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
        name="Time to wakeup",
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
        name="Average heart rate",
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
        name="Minimum heart rate",
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
        name="Light sleep",
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
        name="REM sleep",
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
        name="Average respiratory rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_RESPIRATORY_RATE_MAX.value,
        measurement=Measurement.SLEEP_RESPIRATORY_RATE_MAX,
        measure_type=GetSleepSummaryField.RR_MAX,
        name="Maximum respiratory rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_RESPIRATORY_RATE_MIN.value,
        measurement=Measurement.SLEEP_RESPIRATORY_RATE_MIN,
        measure_type=GetSleepSummaryField.RR_MIN,
        name="Minimum respiratory rate",
        native_unit_of_measurement=UOM_BREATHS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_SCORE.value,
        measurement=Measurement.SLEEP_SCORE,
        measure_type=GetSleepSummaryField.SLEEP_SCORE,
        name="Sleep score",
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
        name="Snoring",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_SNORING_EPISODE_COUNT.value,
        measurement=Measurement.SLEEP_SNORING_EPISODE_COUNT,
        measure_type=GetSleepSummaryField.SNORING_EPISODE_COUNT,
        name="Snoring episode count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        update_type=UpdateType.POLL,
    ),
    WithingsSensorEntityDescription(
        key=Measurement.SLEEP_WAKEUP_COUNT.value,
        measurement=Measurement.SLEEP_WAKEUP_COUNT,
        measure_type=GetSleepSummaryField.WAKEUP_COUNT,
        name="Wakeup count",
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
        name="Wakeup time",
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
