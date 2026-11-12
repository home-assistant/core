"""Sensors for Baby Tracker (Nighp)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pybabytracker import Record

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BabyData, BabyTrackerConfigEntry, BabyTrackerCoordinator
from .entity import BabyTrackerBabyEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BabyTrackerSensorDescription(SensorEntityDescription):
    """A sensor for one kind of record."""

    record_fn: Callable[[BabyData], Record | None]


SENSORS: tuple[BabyTrackerSensorDescription, ...] = (
    BabyTrackerSensorDescription(
        key="last_diaper",
        translation_key="last_diaper",
        device_class=SensorDeviceClass.TIMESTAMP,
        record_fn=lambda baby: baby.diaper,
    ),
    BabyTrackerSensorDescription(
        key="last_feed",
        translation_key="last_feed",
        device_class=SensorDeviceClass.TIMESTAMP,
        record_fn=lambda baby: baby.feed,
    ),
    BabyTrackerSensorDescription(
        key="last_sleep",
        translation_key="last_sleep",
        device_class=SensorDeviceClass.TIMESTAMP,
        record_fn=lambda baby: baby.sleep,
    ),
)


class BabyTrackerSensor(BabyTrackerBabyEntity, SensorEntity):
    """When a baby's last diaper, feed, or sleep happened."""

    entity_description: BabyTrackerSensorDescription

    @property
    def _record(self) -> Record | None:
        baby = self._baby
        return self.entity_description.record_fn(baby) if baby is not None else None

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the time of the baby's newest matching record."""
        record = self._record
        return record.time if record is not None else None


BABY_SENSORS: tuple[
    tuple[tuple[SensorEntityDescription, ...], type[BabyTrackerBabyEntity]], ...
] = ((SENSORS, BabyTrackerSensor),)


def _baby_sensors(
    coordinator: BabyTrackerCoordinator, baby_ids: Iterable[str]
) -> list[BabyTrackerBabyEntity]:
    """Return every sensor of each of the babies."""
    return [
        entity_class(coordinator, description, baby_id)
        for baby_id in baby_ids
        for descriptions, entity_class in BABY_SENSORS
        for description in descriptions
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BabyTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors of every baby on the account."""
    coordinator = entry.runtime_data
    async_add_entities(_baby_sensors(coordinator, coordinator.data.babies))
