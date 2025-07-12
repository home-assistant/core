"""Sensor for door state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HuumDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up door sensor."""
    async_add_entities(
        [HuumDoorSensor(hass.data[DOMAIN][entry.entry_id], entry.entry_id)],
        True,
    )


class HuumDoorSensor(CoordinatorEntity[HuumDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a BinarySensor."""

    _attr_has_entity_name = True
    _attr_name = "Door"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator: HuumDataUpdateCoordinator, unique_id: str) -> None:
        """Initialize the BinarySensor."""
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_unique_id = f"{unique_id}_door"
        self._attr_device_info = coordinator.device_info

        self._coordinator = coordinator

    @property
    def is_on(self) -> bool | None:
        """Return the current value."""
        return not self._coordinator.data.door_closed
