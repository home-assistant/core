"""Base entity for the Snoo integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SnooCoordinator


class SnooDescriptionEntity(CoordinatorEntity[SnooCoordinator]):
    """Defines an Snoo entity that uses a description."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SnooCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the Snoo entity."""
        super().__init__(coordinator)
        self.device = coordinator.device
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_unique_id)},
            name=self.device.name,
            manufacturer="Happiest Baby",
            model="Snoo",
            serial_number=self.device.serialNumber,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None and super().available
