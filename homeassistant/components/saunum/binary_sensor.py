"""Binary sensor platform for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pysaunum import SaunumData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry
from .entity import LeilSaunaEntity

if TYPE_CHECKING:
    from .coordinator import LeilSaunaCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LeilSaunaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Leil Sauna binary sensor entity."""

    value_fn: Callable[[SaunumData], bool | None]


BINARY_SENSORS: tuple[LeilSaunaBinarySensorEntityDescription, ...] = (
    LeilSaunaBinarySensorEntityDescription(
        key="door_open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data.door_open,
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_door_open",
        translation_key="alarm_door_open",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarm_door_open,
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_door_sensor",
        translation_key="alarm_door_sensor",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarm_door_sensor,
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_thermal_cutoff",
        translation_key="alarm_thermal_cutoff",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarm_thermal_cutoff,
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_internal_temp",
        translation_key="alarm_internal_temp",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarm_internal_temp,
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_temp_sensor_short",
        translation_key="alarm_temp_sensor_short",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarm_temp_sensor_short,
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_temp_sensor_open",
        translation_key="alarm_temp_sensor_open",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarm_temp_sensor_open,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna binary sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSORS
        if description.value_fn(coordinator.data) is not None
    )


class LeilSaunaBinarySensorEntity(LeilSaunaEntity, BinarySensorEntity):
    """Representation of a Saunum Leil Sauna binary sensor."""

    entity_description: LeilSaunaBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
