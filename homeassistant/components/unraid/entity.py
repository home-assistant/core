"""Base entity for Unraid integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from .coordinator import UnraidSystemCoordinator


class UnraidSystemEntity(CoordinatorEntity["UnraidSystemCoordinator"]):
    """Base class for Unraid system entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        server_uuid: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the system entity."""
        super().__init__(coordinator)
        self._server_uuid = server_uuid
        self._attr_device_info = device_info
