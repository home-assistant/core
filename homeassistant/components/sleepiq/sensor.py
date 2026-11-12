"""Support for SleepIQ sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, tzinfo
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
from homeassistant.util import dt as dt_util

from .const import (
    BEDTIME,
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
    WAKE_TIME,
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

    value_fn: Callable[[SleepIQSleeper, tzinfo | None], float | int | datetime | None]


def _session_time(value: str | None, time_zone: tzinfo | None) -> datetime | None:
    """Return a session time, which the API reports in the bed's local time."""
    if not value or time_zone is None:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=time_zone)


BED_SENSORS: tuple[SleepIQSensorEntityDescription, ...] = (
    SleepIQSensorEntityDescription(
        key=PRESSURE,
        translation_key="pressure",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sleeper, time_zone: sleeper.pressure,
    ),
    SleepIQSensorEntityDescription(
        key=SLEEP_NUMBER,
        translation_key="sleep_number",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sleeper, time_zone: sleeper.sleep_number,
    ),
)

SLEEP_HEALTH_SENSORS: tuple[SleepIQSensorEntityDescription, ...] = (
    SleepIQSensorEntityDescription(
        key=SLEEP_SCORE,
        translation_key="sleep_score",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="score",
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.sleep_score,
    ),
    SleepIQSensorEntityDescription(
        key=SLEEP_DURATION,
        translation_key="sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda sleeper, time_zone: (
            round(sleeper.sleep_data.duration / 3600, 1)
            if sleeper.sleep_data.duration
            else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key=HEART_RATE,
        translation_key="heart_rate_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.heart_rate,
    ),
    SleepIQSensorEntityDescription(
        key=RESPIRATORY_RATE,
        translation_key="respiratory_rate_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.respiratory_rate,
    ),
    SleepIQSensorEntityDescription(
        key=HRV,
        translation_key="hrv",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.hrv,
    ),
    SleepIQSensorEntityDescription(
        key=BEDTIME,
        translation_key="bedtime",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sleeper, time_zone: _session_time(
            sleeper.sleep_data.start_date, time_zone
        ),
    ),
    SleepIQSensorEntityDescription(
        key=WAKE_TIME,
        translation_key="wake_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sleeper, time_zone: _session_time(
            sleeper.sleep_data.end_date, time_zone
        ),
    ),
    SleepIQSensorEntityDescription(
        key=RESTFUL,
        translation_key="restful",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.restful,
    ),
    SleepIQSensorEntityDescription(
        key=RESTLESS,
        translation_key="restless",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.restless,
    ),
    SleepIQSensorEntityDescription(
        key=OUT_OF_BED,
        translation_key="out_of_bed",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.out_of_bed,
    ),
    SleepIQSensorEntityDescription(
        key=FALL_ASLEEP,
        translation_key="fall_asleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda sleeper, time_zone: sleeper.sleep_data.fall_asleep_period,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SleepIQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data = entry.runtime_data
    # Resolved here because loading an uncached zone reads files.
    time_zones = {
        bed.id: await dt_util.async_get_time_zone(bed.timezone)
        if bed.timezone
        else None
        for bed in data.client.beds.values()
    }

    entities: list[SensorEntity] = []

    entities.extend(
        SleepIQSensorEntity(
            data.data_coordinator, bed, sleeper, description, time_zones[bed.id]
        )
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for description in BED_SENSORS
    )

    entities.extend(
        SleepIQSensorEntity(
            data.sleep_data_coordinator,
            bed,
            sleeper,
            description,
            time_zones[bed.id],
        )
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
        time_zone: tzinfo | None,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._time_zone = time_zone
        super().__init__(coordinator, bed, sleeper, description.key)

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.entity_description.value_fn(
            self.sleeper, self._time_zone
        )
