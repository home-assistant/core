"""Support for CatGenie sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from catgenie import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CatGenieConfigEntry
from .entity import CatGenieEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CatGenieSensorDescription(SensorEntityDescription):
    """Describe a CatGenie sensor."""

    value_fn: Callable[[Device], int | str | datetime | None]


SENSOR_DESCRIPTIONS: tuple[CatGenieSensorDescription, ...] = (
    CatGenieSensorDescription(
        key="sani_solution",
        translation_key="sani_solution",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.remaining_sani_solution,
    ),
    CatGenieSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "cleaning"],
        value_fn=lambda device: "cleaning" if device.is_cleaning else "idle",
    ),
    CatGenieSensorDescription(
        key="clean_progress",
        translation_key="clean_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: (
            device.operation_status.clean_progress_pct if device.is_cleaning else None
        ),
    ),
    CatGenieSensorDescription(
        key="total_cycles",
        translation_key="total_cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.configuration.total_cycles,
    ),
    CatGenieSensorDescription(
        key="last_clean",
        translation_key="last_clean",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.last_clean,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CatGenieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up CatGenie sensors based on a config entry."""
    async_add_entities(
        CatGenieSensorEntity(coordinator, description)
        for coordinator in entry.runtime_data.device_coordinators.values()
        for description in SENSOR_DESCRIPTIONS
    )


class CatGenieSensorEntity(CatGenieEntity, SensorEntity):
    """Defines a CatGenie sensor."""

    entity_description: CatGenieSensorDescription

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
