"""Base entity class for DROP entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DROPDeviceDataUpdateCoordinator


class DROPEntity(CoordinatorEntity[DROPDeviceDataUpdateCoordinator]):
    """Representation of a DROP device entity."""

    _attr_force_update = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entity_type: str, coordinator: DROPDeviceDataUpdateCoordinator
    ) -> None:
        """Init DROP entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{entity_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=self.coordinator.manufacturer,
            model=self.coordinator.model,
            name=self.coordinator.device_name,
        )
