"""Base class for the everHome integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, ATTR_MODEL, DOMAIN
from .coordinator import EcoTrackerDataUpdateCoordinator


class EcoTrackerEntity(CoordinatorEntity[EcoTrackerDataUpdateCoordinator]):
    """Base entity for EcoTracker."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: EcoTrackerDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            manufacturer=ATTR_MANUFACTURER,
            model=ATTR_MODEL,
            sw_version=coordinator.firmware,
            serial_number=coordinator.serial,
        )
