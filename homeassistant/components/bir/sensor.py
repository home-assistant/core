"""Sensor platform for the BIR integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BirConfigEntry
from .entity import BirEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BirSensorDescription(SensorEntityDescription):
    """Describe a BIR sensor."""

    waste_type: str


SENSORS: tuple[BirSensorDescription, ...] = (
    BirSensorDescription(
        key="mixed_waste",
        translation_key="mixed_waste_pickup",
        waste_type="mixed_waste",
        device_class=SensorDeviceClass.DATE,
    ),
    BirSensorDescription(
        key="paper_and_plastic",
        translation_key="paper_and_plastic_pickup",
        waste_type="paper_and_plastic",
        device_class=SensorDeviceClass.DATE,
    ),
    BirSensorDescription(
        key="food_waste",
        translation_key="food_waste_pickup",
        waste_type="food_waste",
        device_class=SensorDeviceClass.DATE,
    ),
    BirSensorDescription(
        key="glass_and_metal_packaging",
        translation_key="glass_and_metal_packaging_pickup",
        waste_type="glass_and_metal_packaging",
        device_class=SensorDeviceClass.DATE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BIR sensor based on a config entry."""
    async_add_entities(
        BirSensor(entry, description)
        for description in SENSORS
        if description.waste_type in entry.runtime_data.data
    )


class BirSensor(BirEntity, SensorEntity):
    """Define a BIR sensor."""

    entity_description: BirSensorDescription

    def __init__(
        self,
        entry: BirConfigEntry,
        description: BirSensorDescription,
    ) -> None:
        """Initialize the BIR sensor."""
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data['property_id']}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.entity_description.waste_type in self.coordinator.data
        )

    @property
    def native_value(self) -> date | None:
        """Return the next pickup date."""
        if pickup := self.coordinator.data.get(self.entity_description.waste_type):
            return pickup["date"]
        return None
