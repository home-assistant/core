"""Sensor platform for fressnapf_tracker."""

from collections.abc import Callable
from dataclasses import dataclass

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

from . import FressnapfTrackerConfigEntry
from .entity import FressnapfTrackerEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FressnapfTrackerSensorDescription(SensorEntityDescription):
    """Class describing Fressnapf Tracker sensor entities."""

    value_fn: Callable[[Tracker], int]


SENSOR_ENTITY_DESCRIPTIONS: tuple[FressnapfTrackerSensorDescription, ...] = (
    FressnapfTrackerSensorDescription(
        key="battery",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery,
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
    def native_value(self) -> int:
        """Return the state of the resources if it has been received yet."""
        return self.entity_description.value_fn(self.coordinator.data)
