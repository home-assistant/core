"""Base entity for Seko Pooldose integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PooldoseCoordinator


class PooldoseEntity(CoordinatorEntity[PooldoseCoordinator]):
    """Base class for all Pooldose entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        serial_number: str,
        device_info_dict: DeviceInfo,
    ) -> None:
        """Initialize the base Pooldose entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_{self.entity_description.key}"
        self._attr_device_info = device_info_dict
