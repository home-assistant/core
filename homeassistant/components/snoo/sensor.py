"""Support for Snoo Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from python_snoo.containers import BabyData, SnooData, SnooStates

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SnooConfigEntry
from .entity import SnooBabyDescriptionEntity, SnooDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class SnooSensorEntityDescription(SensorEntityDescription):
    """Describes a Snoo sensor."""

    value_fn: Callable[[SnooData], StateType]


@dataclass(frozen=True, kw_only=True)
class SnooBabySensorEntityDescription(SensorEntityDescription):
    """Describes a Snoo baby sensor."""

    value_fn: Callable[[BabyData], StateType]


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
        value_fn=lambda data: data.state_machine.time_left_timestamp,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


BABY_SENSOR_DESCRIPTIONS: list[SnooBabySensorEntityDescription] = [
    SnooBabySensorEntityDescription(
        key="minimal_level",
        translation_key="minimal_level",
        icon="mdi:minus",
        value_fn=lambda data: data.settings.minimalLevel,
    ),
    SnooBabySensorEntityDescription(
        key="minimal_level_volume",
        translation_key="minimal_level_volume",
        icon="mdi:volume-low",
        value_fn=lambda data: data.settings.minimalLevelVolume,
    ),
    SnooBabySensorEntityDescription(
        key="responsiveness_level",
        translation_key="responsiveness_level",
        icon="mdi:knob",
        value_fn=lambda data: data.settings.responsivenessLevel,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Snoo device sensors."""
    coordinators = entry.runtime_data

    sensors: list[SensorEntity] = []
    for coordinator in coordinators.values():
        sensors.extend(
            SnooSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
        )

        sensors.extend(
            SnooBabySensor(baby_coordinator, description)
            for baby_coordinator in coordinator.baby_coordinators.values()
            for description in BABY_SENSOR_DESCRIPTIONS
        )

    async_add_entities(sensors)


class SnooSensor(SnooDescriptionEntity, SensorEntity):
    """A sensor using Snoo coordinator."""

    entity_description: SnooSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class SnooBabySensor(SnooBabyDescriptionEntity, SensorEntity):
    """A baby sensor using Snoo baby coordinator."""

    entity_description: SnooBabySensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
