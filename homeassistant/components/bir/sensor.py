"""Sensor platform for the BIR integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_PROPERTY_ID
from .coordinator import BirConfigEntry, WastePickup
from .entity import BirEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BirSensorDescription(SensorEntityDescription):
    """Describe a BIR sensor."""

    waste_type: str
    value_fn: Callable[[WastePickup], date | int]


DATE_SENSORS: tuple[BirSensorDescription, ...] = (
    BirSensorDescription(
        key="mixed_waste_date",
        translation_key="mixed_waste_pickup",
        waste_type="mixed_waste",
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=lambda pickup: pickup["date"],
    ),
    BirSensorDescription(
        key="paper_and_plastic_date",
        translation_key="paper_and_plastic_pickup",
        waste_type="paper_and_plastic",
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=lambda pickup: pickup["date"],
    ),
    BirSensorDescription(
        key="food_waste_date",
        translation_key="food_waste_pickup",
        waste_type="food_waste",
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=lambda pickup: pickup["date"],
    ),
    BirSensorDescription(
        key="glass_and_metal_packaging_date",
        translation_key="glass_and_metal_packaging_pickup",
        waste_type="glass_and_metal_packaging",
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=lambda pickup: pickup["date"],
    ),
)

DAYS_UNTIL_SENSORS: tuple[BirSensorDescription, ...] = (
    BirSensorDescription(
        key="mixed_waste_days_until",
        translation_key="mixed_waste_days_until",
        waste_type="mixed_waste",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda pickup: pickup["days_until"],
    ),
    BirSensorDescription(
        key="paper_and_plastic_days_until",
        translation_key="paper_and_plastic_days_until",
        waste_type="paper_and_plastic",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda pickup: pickup["days_until"],
    ),
    BirSensorDescription(
        key="food_waste_days_until",
        translation_key="food_waste_days_until",
        waste_type="food_waste",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda pickup: pickup["days_until"],
    ),
    BirSensorDescription(
        key="glass_and_metal_packaging_days_until",
        translation_key="glass_and_metal_packaging_days_until",
        waste_type="glass_and_metal_packaging",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda pickup: pickup["days_until"],
    ),
)

SENSORS: tuple[BirSensorDescription, ...] = DATE_SENSORS + DAYS_UNTIL_SENSORS


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
        self._attr_unique_id = f"{entry.data[CONF_PROPERTY_ID]}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.entity_description.waste_type in self.coordinator.data
        )

    @property
    def native_value(self) -> date | int | None:
        """Return the sensor value."""
        if pickup := self.coordinator.data.get(self.entity_description.waste_type):
            return self.entity_description.value_fn(pickup)
        return None
