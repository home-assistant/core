"""Hanna Instruments entity base class for Home Assistant.

This module provides the base entity class for Hanna Instruments entities.
"""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HannaDataCoordinator


class HannaEntity(CoordinatorEntity[HannaDataCoordinator], Entity):
    """Base class for Hanna entities."""

    def __init__(self, coordinator: HannaDataCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for Home Assistant."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_identifier)},
            manufacturer=self.coordinator.device_data.get("manufacturer"),
            model=self.coordinator.device_data.get("DM"),
            name=self.coordinator.device_data.get("name"),
            serial_number=self.coordinator.device_data.get("serial_number"),
            sw_version=self.coordinator.device_data.get("sw_version"),
        )
