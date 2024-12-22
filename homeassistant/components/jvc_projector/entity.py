"""Base Entity for the jvc_projector integration."""

from __future__ import annotations

import logging

from jvcprojector.projector import JvcProjector

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import JvcProjectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class JvcProjectorEntity(CoordinatorEntity[JvcProjectorDataUpdateCoordinator]):
    """Defines a base JVC Projector entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: JvcProjectorDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = coordinator.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            name=NAME,
            model=self.device.model,
            manufacturer=MANUFACTURER,
            sw_version=self.device.version,
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
        )

    @property
    def device(self) -> JvcProjector:
        """Return the device representing the projector."""
        return self.coordinator.device

    @staticmethod
    def has_eshift(entity: JvcProjectorEntity) -> bool:
        """Return if device has e-shift."""
        return "NZ" in entity.device.model

    @staticmethod
    def has_laser(entity: JvcProjectorEntity) -> bool:
        """Return if device has laser."""
        return "NZ" in entity.device.model or "NX9" in entity.device.model
