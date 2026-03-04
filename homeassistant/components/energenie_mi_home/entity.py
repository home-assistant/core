"""Base entity for Energenie Mi Home."""

from __future__ import annotations

import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MiHomeCoordinator

_LOGGER = logging.getLogger(__name__)

# Device manufacturer info
MANUFACTURER = "Energenie"
MODEL = "Mi Home Device"


class MiHomeEntity(CoordinatorEntity[MiHomeCoordinator]):
    """Base entity for Mi Home devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MiHomeCoordinator, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        device = self.coordinator.data.get(self.device_id)
        if device:
            return DeviceInfo(
                identifiers={(DOMAIN, self.device_id)},
                name=device.name,
                manufacturer=MANUFACTURER,
                model=device.product_type or device.device_type,
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name="Unknown Device",
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        coordinator_available = super().available
        if not coordinator_available:
            _LOGGER.debug(
                "Entity %s unavailable: coordinator not available", self.device_id
            )
            return False
        device = self.coordinator.data.get(self.device_id)
        if device is None:
            _LOGGER.debug(
                "Entity %s unavailable: device not found in coordinator data (available devices: %s)",
                self.device_id,
                list(self.coordinator.data.keys()) if self.coordinator.data else "none",
            )
            return False
        if not device.available:
            _LOGGER.debug(
                "Entity %s unavailable: device.available is False", self.device_id
            )
            return False
        return True
