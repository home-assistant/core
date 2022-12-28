"""Base Entity for the JVC Projector integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN as JVC_DOMAIN,
    MANUFACTURER as JVC_MANUFACTURER,
    NAME as JVC_NAME,
)
from .coordinator import JvcProjectorDataUpdateCoordinator

if TYPE_CHECKING:
    from jvcprojector import JvcProjector

_LOGGER = logging.getLogger(__name__)


class JvcProjectorEntity(CoordinatorEntity[JvcProjectorDataUpdateCoordinator]):
    """Defines a base JVC Projector entity."""

    def __init__(self, coordinator: JvcProjectorDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = self.device.mac
        self._attr_name = JVC_NAME
        self._attr_device_info = DeviceInfo(
            identifiers={(JVC_DOMAIN, self.device.mac)},
            name=self.name,
            model=self.device.model,
            manufacturer=JVC_MANUFACTURER,
            suggested_area="Theater",
        )

    @property
    def device(self) -> JvcProjector:
        """Return the device representing the projector."""
        return self.coordinator.device
