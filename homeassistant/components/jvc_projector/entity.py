"""Base Entity for the jvc_projector integration."""

from __future__ import annotations

import logging

from jvcprojector import JvcProjector

from homeassistant.helpers.device_registry import DeviceInfo
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
        )

    @property
    def device(self) -> JvcProjector:
        """Return the device representing the projector."""
        return self.coordinator.device
