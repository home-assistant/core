"""Sensor platform for fressnapf_tracker."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import override

from fressnapftracker import Tracker

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import FressnapfTrackerConfigEntry
from .entity import FressnapfTrackerEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an API timestamp, assuming UTC if it has no timezone."""
    if value is None:
        return None
    try:
        parsed = dt_util.parse_datetime(value, raise_on_error=True)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


@dataclass(frozen=True, kw_only=True)
class FressnapfTrackerSensorDescription(SensorEntityDescription):
    """Class describing Fressnapf Tracker sensor entities."""

    value_fn: Callable[[Tracker], int | datetime | None]


SENSOR_ENTITY_DESCRIPTIONS: tuple[FressnapfTrackerSensorDescription, ...] = (
    FressnapfTrackerSensorDescription(
        key="battery",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery,
    ),
    FressnapfTrackerSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _parse_timestamp(data.last_seen_timestamp),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FressnapfTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fressnapf Tracker sensors."""

    async_add_entities(
        FressnapfTrackerSensor(coordinator, sensor_description)
        for sensor_description in SENSOR_ENTITY_DESCRIPTIONS
        for coordinator in entry.runtime_data
    )


class FressnapfTrackerSensor(FressnapfTrackerEntity, SensorEntity):
    """fressnapf_tracker sensor for general information."""

    entity_description: FressnapfTrackerSensorDescription

    @property
    @override
    def native_value(self) -> int | datetime | None:
        """Return the state of the resources if it has been received yet."""
        return self.entity_description.value_fn(self.coordinator.data)
