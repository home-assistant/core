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
from .entity import CatGenieEntity, CatGenieEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CatGenieSensorDescription(CatGenieEntityDescription, SensorEntityDescription):
    """Describe a CatGenie sensor."""

    value_fn: Callable[[Device], int | str | datetime | None]


SENSOR_DESCRIPTIONS: tuple[CatGenieSensorDescription, ...] = (
    CatGenieSensorDescription(
        key="sani_solution",
        translation_key="sani_solution",
        native_unit_of_measurement="cycles",
        value_fn=lambda device: device.remaining_sani_solution,
    ),
    CatGenieSensorDescription(
        key="clean_progress",
        translation_key="clean_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda device: device.is_cleaning,
        value_fn=lambda device: device.operation_status.clean_progress_pct,
    ),
    CatGenieSensorDescription(
        key="total_cycles",
        translation_key="total_cycles",
        native_unit_of_measurement="cycles",
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
    coordinator = entry.runtime_data.coordinator
    known_device_ids: set[str] = set()

    def _async_add_new_devices() -> None:
        """Add entities for any newly discovered devices."""
        new_device_ids = set(coordinator.data) - known_device_ids
        if new_device_ids:
            async_add_entities(
                CatGenieSensorEntity(coordinator, description, device_id)
                for device_id in new_device_ids
                for description in SENSOR_DESCRIPTIONS
            )
            known_device_ids.update(new_device_ids)

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class CatGenieSensorEntity(CatGenieEntity, SensorEntity):
    """Defines a CatGenie sensor."""

    entity_description: CatGenieSensorDescription

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device_data)
