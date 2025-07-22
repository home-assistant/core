"""Base entity class for Olarm entities."""

from __future__ import annotations

import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OlarmDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class OlarmEntity(CoordinatorEntity[OlarmDataUpdateCoordinator]):
    """Base class for Olarm entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OlarmDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the Olarm entity."""
        super().__init__(coordinator)
        self.device_id = device_id

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.device_name,
            manufacturer="Olarm",
        )
