"""Base entity class for DROP entities."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DROPDeviceDataUpdateCoordinator


class DROPEntity(CoordinatorEntity[DROPDeviceDataUpdateCoordinator]):
    """Representation of a DROP device entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entity_type: str, coordinator: DROPDeviceDataUpdateCoordinator
    ) -> None:
        """Init DROP entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_type}"
        self._attr_device_info = coordinator.device_info
