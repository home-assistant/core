"""Support for SleepIQ sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PRESSURE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    FALL_ASLEEP,
    HEART_RATE,
    HRV,
    OUT_OF_BED,
    RESPIRATORY_RATE,
    RESTFUL,
    RESTLESS,
    SLEEP_DURATION,
    SLEEP_NUMBER,
    SLEEP_SCORE,
)
from .coordinator import (
    SleepIQConfigEntry,
    SleepIQDataUpdateCoordinator,
    SleepIQSleepDataCoordinator,
)
from .entity import SleepIQSleeperEntity


@dataclass(frozen=True, kw_only=True)
class SleepIQSensorEntityDescription(SensorEntityDescription):
    """Describes SleepIQ sensor entity."""

    value_fn: Callable[[SleepIQSleeper], float | int | None]


BED_SENSORS: tuple[SleepIQSensorEntityDescription, ...] = (
    SleepIQSensorEntityDescription(
        key=PRESSURE,
        translation_key="pressure",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sleeper: sleeper.pressure,
    ),
    SleepIQSensorEntityDescription(
        key=SLEEP_NUMBER,
        translation_key="sleep_number",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sleeper: sleeper.sleep_number,
    ),
)

SLEEP_HEALTH_SENSORS: tuple[SleepIQSensorEntityDescription, ...] = (
    SleepIQSensorEntityDescription(
        key=SLEEP_SCORE,
        translation_key="sleep_score",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="score",
        value_fn=lambda sleeper: (
            sleeper.sleep_data.sleep_score if sleeper.sleep_data else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=SLEEP_DURATION,
        translation_key="sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda sleeper: (
            round(sleeper.sleep_data.duration / 3600, 1)
            if sleeper.sleep_data and sleeper.sleep_data.duration
            else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=HEART_RATE,
        translation_key="heart_rate_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        value_fn=lambda sleeper: (
            sleeper.sleep_data.heart_rate if sleeper.sleep_data else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=RESPIRATORY_RATE,
        translation_key="respiratory_rate_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        value_fn=lambda sleeper: (
            sleeper.sleep_data.respiratory_rate if sleeper.sleep_data else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=HRV,
        translation_key="hrv",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        value_fn=lambda sleeper: sleeper.sleep_data.hrv if sleeper.sleep_data else None,
    ),
    SleepIQSensorEntityDescription(
        key=RESTFUL,
        translation_key="restful",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper: (
            sleeper.sleep_data.restful if sleeper.sleep_data else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=RESTLESS,
        translation_key="restless",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper: (
            sleeper.sleep_data.restless if sleeper.sleep_data else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=OUT_OF_BED,
        translation_key="out_of_bed",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper: (
            sleeper.sleep_data.out_of_bed if sleeper.sleep_data else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=FALL_ASLEEP,
        translation_key="fall_asleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper: (
            sleeper.sleep_data.fall_asleep_period if sleeper.sleep_data else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SleepIQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data = entry.runtime_data

    entities: list[SensorEntity] = []

    entities.extend(
        SleepIQSensorEntity(data.data_coordinator, bed, sleeper, description)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for description in BED_SENSORS
    )

    entities.extend(
        SleepIQSensorEntity(data.sleep_data_coordinator, bed, sleeper, description)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for description in SLEEP_HEALTH_SENSORS
    )

    async_add_entities(entities)


class SleepIQSensorEntity(
    SleepIQSleeperEntity[SleepIQDataUpdateCoordinator | SleepIQSleepDataCoordinator],
    SensorEntity,
):
    """Representation of a SleepIQ sensor."""

    # Icons come from icons.json, which the inherited bed icon would override.
    _attr_icon = None
    entity_description: SleepIQSensorEntityDescription

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator | SleepIQSleepDataCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        description: SleepIQSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(coordinator, bed, sleeper, description.key)

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.entity_description.value_fn(self.sleeper)
