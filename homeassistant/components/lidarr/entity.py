"""The Lidarr component."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LidarrDataUpdateCoordinator, T


class LidarrEntity(CoordinatorEntity[LidarrDataUpdateCoordinator[T]]):
    """Defines a base Lidarr entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LidarrDataUpdateCoordinator[T],
        description: EntityDescription,
    ) -> None:
        """Initialize the Lidarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)}
        )
