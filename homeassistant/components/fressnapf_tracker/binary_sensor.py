"""Binary Sensor platform for fressnapf_tracker."""

from collections.abc import Callable
from dataclasses import dataclass

from fressnapftracker import Tracker

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FressnapfTrackerConfigEntry
from .entity import FressnapfTrackerEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FressnapfTrackerBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing Fressnapf Tracker binary_sensor entities."""

    value_fn: Callable[[Tracker], bool]


BINARY_SENSOR_ENTITY_DESCRIPTIONS: tuple[
    FressnapfTrackerBinarySensorDescription, ...
] = (
    FressnapfTrackerBinarySensorDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FressnapfTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fressnapf Tracker binary_sensors."""

    async_add_entities(
        FressnapfTrackerBinarySensor(coordinator, sensor_description)
        for sensor_description in BINARY_SENSOR_ENTITY_DESCRIPTIONS
        for coordinator in entry.runtime_data
    )


class FressnapfTrackerBinarySensor(FressnapfTrackerEntity, BinarySensorEntity):
    """Fressnapf Tracker binary_sensor for general information."""

    entity_description: FressnapfTrackerBinarySensorDescription

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
