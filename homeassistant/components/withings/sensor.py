"""Sensors flow for Withings."""
from __future__ import annotations

from withings_api.common import GetSleepSummaryField, MeasureType

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    MASS_KILOGRAMS,
    PERCENTAGE,
    SPEED_METERS_PER_SECOND,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    BaseWithingsSensor,
    UpdateType,
    WithingsAttribute,
    async_get_data_manager,
)
from .const import (
    SCORE_POINTS,
    UOM_BEATS_PER_MINUTE,
    UOM_BREATHS_PER_MINUTE,
    UOM_FREQUENCY,
    UOM_LENGTH_M,
    UOM_MMHG,
    UOM_TEMP_C,
    Measurement,
)

SENSORS = [
    WithingsAttribute(
        Measurement.WEIGHT_KG,
        MeasureType.WEIGHT,
        "Weight",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.FAT_MASS_KG,
        MeasureType.FAT_MASS_WEIGHT,
        "Fat Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.FAT_FREE_MASS_KG,
        MeasureType.FAT_FREE_MASS,
        "Fat Free Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.MUSCLE_MASS_KG,
        MeasureType.MUSCLE_MASS,
        "Muscle Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.BONE_MASS_KG,
        MeasureType.BONE_MASS,
        "Bone Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.HEIGHT_M,
        MeasureType.HEIGHT,
        "Height",
        UOM_LENGTH_M,
        "mdi:ruler",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.TEMP_C,
        MeasureType.TEMPERATURE,
        "Temperature",
        UOM_TEMP_C,
        "mdi:thermometer",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.BODY_TEMP_C,
        MeasureType.BODY_TEMPERATURE,
        "Body Temperature",
        UOM_TEMP_C,
        "mdi:thermometer",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SKIN_TEMP_C,
        MeasureType.SKIN_TEMPERATURE,
        "Skin Temperature",
        UOM_TEMP_C,
        "mdi:thermometer",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.FAT_RATIO_PCT,
        MeasureType.FAT_RATIO,
        "Fat Ratio",
        PERCENTAGE,
        None,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.DIASTOLIC_MMHG,
        MeasureType.DIASTOLIC_BLOOD_PRESSURE,
        "Diastolic Blood Pressure",
        UOM_MMHG,
        None,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SYSTOLIC_MMGH,
        MeasureType.SYSTOLIC_BLOOD_PRESSURE,
        "Systolic Blood Pressure",
        UOM_MMHG,
        None,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.HEART_PULSE_BPM,
        MeasureType.HEART_RATE,
        "Heart Pulse",
        UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SPO2_PCT,
        MeasureType.SP02,
        "SP02",
        PERCENTAGE,
        None,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.HYDRATION,
        MeasureType.HYDRATION,
        "Hydration",
        MASS_KILOGRAMS,
        "mdi:water",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.PWV,
        MeasureType.PULSE_WAVE_VELOCITY,
        "Pulse Wave Velocity",
        SPEED_METERS_PER_SECOND,
        None,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY,
        GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY,
        "Breathing disturbances intensity",
        "",
        "",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_DEEP_DURATION_SECONDS,
        GetSleepSummaryField.DEEP_SLEEP_DURATION,
        "Deep sleep",
        TIME_SECONDS,
        "mdi:sleep",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_TOSLEEP_DURATION_SECONDS,
        GetSleepSummaryField.DURATION_TO_SLEEP,
        "Time to sleep",
        TIME_SECONDS,
        "mdi:sleep",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS,
        GetSleepSummaryField.DURATION_TO_WAKEUP,
        "Time to wakeup",
        TIME_SECONDS,
        "mdi:sleep-off",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_HEART_RATE_AVERAGE,
        GetSleepSummaryField.HR_AVERAGE,
        "Average heart rate",
        UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_HEART_RATE_MAX,
        GetSleepSummaryField.HR_MAX,
        "Maximum heart rate",
        UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_HEART_RATE_MIN,
        GetSleepSummaryField.HR_MIN,
        "Minimum heart rate",
        UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_LIGHT_DURATION_SECONDS,
        GetSleepSummaryField.LIGHT_SLEEP_DURATION,
        "Light sleep",
        TIME_SECONDS,
        "mdi:sleep",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_REM_DURATION_SECONDS,
        GetSleepSummaryField.REM_SLEEP_DURATION,
        "REM sleep",
        TIME_SECONDS,
        "mdi:sleep",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE,
        GetSleepSummaryField.RR_AVERAGE,
        "Average respiratory rate",
        UOM_BREATHS_PER_MINUTE,
        None,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_RESPIRATORY_RATE_MAX,
        GetSleepSummaryField.RR_MAX,
        "Maximum respiratory rate",
        UOM_BREATHS_PER_MINUTE,
        None,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_RESPIRATORY_RATE_MIN,
        GetSleepSummaryField.RR_MIN,
        "Minimum respiratory rate",
        UOM_BREATHS_PER_MINUTE,
        None,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_SCORE,
        GetSleepSummaryField.SLEEP_SCORE,
        "Sleep score",
        SCORE_POINTS,
        "mdi:medal",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_SNORING,
        GetSleepSummaryField.SNORING,
        "Snoring",
        "",
        None,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_SNORING_EPISODE_COUNT,
        GetSleepSummaryField.SNORING_EPISODE_COUNT,
        "Snoring episode count",
        "",
        None,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_WAKEUP_COUNT,
        GetSleepSummaryField.WAKEUP_COUNT,
        "Wakeup count",
        UOM_FREQUENCY,
        "mdi:sleep-off",
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_WAKEUP_DURATION_SECONDS,
        GetSleepSummaryField.WAKEUP_DURATION,
        "Wakeup time",
        TIME_SECONDS,
        "mdi:sleep-off",
        False,
        UpdateType.POLL,
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

    @property
    def native_value(self) -> None | str | int | float:
        """Return the state of the entity."""
        return self._state_data

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._attribute.unit_of_measurement

    @property
    def state_class(self) -> str:
        """Return the state_class of this entity, if any."""
        return SensorStateClass.MEASUREMENT
