"""Binary sensor platform for SVS Subwoofer."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SVSConfigEntry
from .coordinator import SVSSubwooferCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SVSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SVS binary sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities([SVSConnectionSensor(coordinator)])


class SVSConnectionSensor(
    CoordinatorEntity[SVSSubwooferCoordinator], BinarySensorEntity
):
    """Binary sensor showing Bluetooth connection status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connected"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, coordinator: SVSSubwooferCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_connected"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        return self.coordinator.is_connected

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
