"""Base entity for Watts Vision integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WattsVisionCoordinator


class WattsVisionEntity(CoordinatorEntity[WattsVisionCoordinator]):
    """Base entity for Watts Vision integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WattsVisionCoordinator, device_id: str) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = device_id

        device = coordinator.data.get(device_id)
        if device:
            self._attr_name = getattr(device, "device_name", None)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""

        device = self.coordinator.data.get(self.device_id)
        if device:
            return DeviceInfo(
                identifiers={(DOMAIN, self.device_id)},
                name=device.device_name,
                manufacturer="Watts",
                model=f"Vision+ {device.device_type}",
            )
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.data.get(self.device_id)
        if device:
            return device.is_online
        return False
