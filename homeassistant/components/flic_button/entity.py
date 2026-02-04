"""Base entity for Flic Button integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlicCoordinator


class FlicButtonEntity(CoordinatorEntity[FlicCoordinator]):
    """Base entity for Flic Button integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the Flic button entity.

        Args:
            coordinator: Flic coordinator instance

        """
        super().__init__(coordinator)
        serial = coordinator.serial_number
        if serial:
            device_name = f"{coordinator.model_name} ({serial})"
        else:
            device_name = f"Flic {coordinator.client.address[-5:]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.client.address)},
            name=device_name,
            manufacturer="Shortcut Labs",
            model=coordinator.model_name,
            serial_number=serial,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.connected
