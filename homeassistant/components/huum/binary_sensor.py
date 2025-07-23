"""Sensor for door state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator
from .entity import HuumBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HuumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up door sensor."""
    async_add_entities(
        [HuumDoorSensor(config_entry.runtime_data)],
    )


class HuumDoorSensor(HuumBaseEntity, BinarySensorEntity):
    """Representation of a BinarySensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the BinarySensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_door"

    @property
    def is_on(self) -> bool | None:
        """Return the current value."""
        return not self.coordinator.data.door_closed
