"""Support for Snoo Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from python_snoo.containers import SnooData, SnooStates

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SnooConfigEntry
from .coordinator import SnooCoordinator
from .entity import SnooDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class SnooSensorEntityDescription(SensorEntityDescription):
    """Describes a Snoo binary sensor."""

    value_fn: Callable[[SnooData], bool]


SENSOR_DESCRIPTIONS: list[SnooSensorEntityDescription] = [
    SnooSensorEntityDescription(
        key="state",
        translation_key="state",
        value_fn=lambda data: data.state_machine.state.name,
        device_class=SensorDeviceClass.ENUM,
        options=[e.name for e in SnooStates],
    ),
    SnooSensorEntityDescription(
        key="time_left",
        translation_key="time_left",
        value_fn=lambda data: data.state_machine.time_left,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Snoo device."""
    coordinators: dict[str, SnooCoordinator] = entry.runtime_data
    async_add_entities(
        SnooSensor(coordinator, description)
        for coordinator in coordinators.values()
        for description in SENSOR_DESCRIPTIONS
    )


class SnooSensor(SnooDescriptionEntity, SensorEntity):
    """A sensor using Snoo coordinator."""

    entity_description: SnooSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
