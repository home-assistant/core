"""Base entity for the UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import Door

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UnifiAccessCoordinator


class UnifiAccessEntity(CoordinatorEntity[UnifiAccessCoordinator]):
    """Base entity for UniFi Access doors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._door_id = door.id
        self._attr_unique_id = f"{door.id}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, door.id)},
            name=door.name,
            manufacturer="Ubiquiti",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._door_id in self.coordinator.data.doors

    @property
    def _door(self) -> Door:
        """Return the current door state from coordinator data."""
        return self.coordinator.data.doors[self._door_id]


class UnifiAccessHubEntity(CoordinatorEntity[UnifiAccessCoordinator]):
    """Base entity for hub-level (controller-wide) UniFi Access entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UnifiAccessCoordinator) -> None:
        """Initialize the hub entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="UniFi Access",
            manufacturer="Ubiquiti",
        )
