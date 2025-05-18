"""Tedee sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from aiotedee import TedeeLock

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TedeeConfigEntry
from .entity import TedeeDescriptionEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TedeeSensorEntityDescription(SensorEntityDescription):
    """Describes Tedee sensor entity."""

    value_fn: Callable[[TedeeLock], float | None]


ENTITIES: tuple[TedeeSensorEntityDescription, ...] = (
    TedeeSensorEntityDescription(
        key="battery_sensor",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda lock: lock.battery_level,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TedeeSensorEntityDescription(
        key="pullspring_duration",
        translation_key="pullspring_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda lock: lock.duration_pullspring,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TedeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tedee sensor entity."""
    coordinator = entry.runtime_data

    def _async_add_new_lock(locks: list[TedeeLock]) -> None:
        async_add_entities(
            TedeeSensorEntity(lock, coordinator, entity_description)
            for entity_description in ENTITIES
            for lock in locks
        )

    coordinator.new_lock_callbacks.append(_async_add_new_lock)
    _async_add_new_lock(list(coordinator.data.values()))


class TedeeSensorEntity(TedeeDescriptionEntity, SensorEntity):
    """Tedee sensor entity."""

    entity_description: TedeeSensorEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._lock)
