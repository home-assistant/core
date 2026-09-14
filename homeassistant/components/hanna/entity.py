"""Hanna Instruments entity base class for Home Assistant.

This module provides the base entity class for Hanna Instruments entities.
"""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HannaDataCoordinator


class HannaEntity(CoordinatorEntity[HannaDataCoordinator]):
    """Base class for Hanna entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HannaDataCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_identifier)},
            manufacturer=coordinator.device_data.get("manufacturer"),
            model=coordinator.device_data.get("DM"),
            name=coordinator.device_data.get("name"),
            serial_number=coordinator.device_data.get("serial_number"),
            sw_version=coordinator.device_data.get("sw_version"),
        )
