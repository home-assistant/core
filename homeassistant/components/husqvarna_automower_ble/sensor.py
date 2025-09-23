"""Support for sensor entities."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HusqvarnaConfigEntry
from .entity import HusqvarnaAutomowerBleDescriptorEntity

DESCRIPTIONS = (
    SensorEntityDescription(
        key="battery_level",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HusqvarnaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Husqvarna Automower Ble sensor based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HusqvarnaAutomowerBleSensor(coordinator, description)
        for description in DESCRIPTIONS
        if description.key in coordinator.data
    )


class HusqvarnaAutomowerBleSensor(HusqvarnaAutomowerBleDescriptorEntity, SensorEntity):
    """Representation of a sensor."""

    entity_description: SensorEntityDescription

    @property
    def native_value(self) -> str | int:
        """Return the previously fetched value."""
        return self.coordinator.data[self.entity_description.key]
