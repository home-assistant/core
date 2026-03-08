"""Entity helpers for the Kaiterra integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MODEL, DOMAIN, MANUFACTURER
from .coordinator import KaiterraDataUpdateCoordinator


class KaiterraEntity(CoordinatorEntity[KaiterraDataUpdateCoordinator]):
    """Base entity for Kaiterra."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KaiterraDataUpdateCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=MANUFACTURER,
            model=DEFAULT_MODEL,
            name=coordinator.device_name,
        )
