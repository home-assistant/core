"""Support for SleepIQ sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PRESSURE, SLEEP_NUMBER
from .coordinator import (
    SleepIQData,
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
        key="sleep_score",
        translation_key="sleep_score",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="score",
        value_fn=lambda sleeper: getattr(sleeper, "sleep_score", None),
    ),
    SleepIQSensorEntityDescription(
        key="sleep_duration",
        translation_key="sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda sleeper: (
            round(getattr(sleeper, "sleep_duration", 0) / 3600, 1)
            if getattr(sleeper, "sleep_duration", 0)
            else None
        ),
    ),
    SleepIQSensorEntityDescription(
        key="heart_rate",
        translation_key="heart_rate_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        value_fn=lambda sleeper: getattr(sleeper, "heart_rate", None),
    ),
    SleepIQSensorEntityDescription(
        key="respiratory_rate",
        translation_key="respiratory_rate_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        value_fn=lambda sleeper: getattr(sleeper, "respiratory_rate", None),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    entities.extend(
        SleepIQSensorEntity(
            data.data_coordinator, bed, sleeper, description
        )
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for description in BED_SENSORS
    )

    entities.extend(
        SleepIQSensorEntity(
            data.sleep_data_coordinator, bed, sleeper, description
        )
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for description in SLEEP_HEALTH_SENSORS
    )

    async_add_entities(entities)


class SleepIQSensorEntity(SleepIQSleeperEntity[DataUpdateCoordinator], SensorEntity):
    """Representation of a SleepIQ sensor."""

    entity_description: SleepIQSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        description: SleepIQSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, bed, sleeper, description.key)
        self.entity_description = description

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.entity_description.value_fn(self.sleeper)
