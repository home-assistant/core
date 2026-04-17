"""Base entity for the EARN-E P1 Meter integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EarnEP1Coordinator


class EarnEP1Entity(CoordinatorEntity[EarnEP1Coordinator]):
    """Base class for EARN-E P1 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EarnEP1Coordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.identifier)},
            name="EARN-E P1 Meter",
            manufacturer="EARN-E",
            model=coordinator.model,
            serial_number=coordinator.serial,
            sw_version=coordinator.sw_version,
        )
