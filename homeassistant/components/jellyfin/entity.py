"""Base Entity for Jellyfin."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import JellyfinDataUpdateCoordinator


class JellyfinEntity(CoordinatorEntity[JellyfinDataUpdateCoordinator]):
    """Defines a base Jellyfin entity."""

    _attr_has_entity_name = True


class JellyfinServerEntity(JellyfinEntity):
    """Defines a base Jellyfin server entity."""

    def __init__(self, coordinator: JellyfinDataUpdateCoordinator) -> None:
        """Initialize the Jellyfin entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.server_id)},
            manufacturer=DEFAULT_NAME,
            name=coordinator.server_name,
            sw_version=coordinator.server_version,
        )


class JellyfinClientEntity(JellyfinEntity):
    """Defines a base Jellyfin client entity."""

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        session_id: str,
    ) -> None:
        """Initialize the Jellyfin entity."""
        super().__init__(coordinator)
        self.session_id = session_id
        self.device_id: str = self.session_data["DeviceId"]
        self.device_name: str = self.session_data["DeviceName"]
        self.client_name: str = self.session_data["Client"]
        self.app_version: str = self.session_data["ApplicationVersion"]
        self.capabilities: dict[str, Any] = self.session_data["Capabilities"]

        if self.capabilities.get("SupportsPersistentIdentifier", False):
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device_id)},
                manufacturer="Jellyfin",
                model=self.client_name,
                name=self.device_name,
                sw_version=self.app_version,
                via_device=(DOMAIN, coordinator.server_id),
            )
            self._attr_name = None
        else:
            self._attr_device_info = None
            self._attr_has_entity_name = False
            self._attr_name = self.device_name

    @property
    def session_data(self) -> dict[str, Any]:
        """Return the session data."""
        return self.coordinator.data[self.session_id]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.session_id in self.coordinator.data
