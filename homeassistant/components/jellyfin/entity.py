"""Base Entity for Jellyfin."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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
            identifiers={(DOMAIN, coordinator.server_id)},
        )


class JellyfinClientEntity(JellyfinEntity):
    """Defines a base Jellyfin client entity.

    Persistent devices (SupportsPersistentIdentifier=True) are stored in
    coordinator.known_devices, recreated after HA restarts, and show OFF when
    the device is offline.

    Ephemeral devices (SupportsPersistentIdentifier=False, e.g. web browsers)
    are in coordinator.ephemeral_devices. They show unavailable when offline
    and are not persisted across restarts.
    """

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the Jellyfin entity."""
        super().__init__(coordinator)
        self.device_id: str = device_id

        device_info = (
            coordinator.known_devices.get(device_id)
            or coordinator.ephemeral_devices[device_id]
        )
        self._is_ephemeral: bool = device_id not in coordinator.known_devices
        self.device_name: str = device_info["DeviceName"]
        self.client_name: str = device_info["Client"]
        self.app_version: str = device_info["ApplicationVersion"]
        self.capabilities: dict[str, Any] = device_info.get("Capabilities", {})

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.server_id}-{coordinator.user_id}-{self.device_id}",
                )
            },
            manufacturer="Jellyfin",
            model=self.client_name,
            name=self.device_name,
            sw_version=self.app_version,
            via_device=(DOMAIN, coordinator.server_id),
        )
        self._attr_name = None

    @property
    def session_data(self) -> dict[str, Any] | None:
        """Return active session data, or None if the device is offline."""
        return self.coordinator.data.get(self.device_id)

    @property
    def session_id(self) -> str | None:
        """Return the active session ID, or None if the device is offline."""
        session = self.session_data
        return session["Id"] if session else None

    @property
    def available(self) -> bool:
        """Return True when the device is reachable.

        Persistent devices show state OFF when offline (server is reachable,
        device is just turned off). Ephemeral devices become unavailable when
        their session ends, since they have no stable persistent presence.
        """
        if self._is_ephemeral:
            return super().available and self.device_id in self.coordinator.data
        return super().available
