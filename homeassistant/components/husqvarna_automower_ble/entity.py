"""Provides the HusqvarnaAutomowerBleEntity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HusqvarnaCoordinator


class HusqvarnaAutomowerBleEntity(CoordinatorEntity[HusqvarnaCoordinator]):
    """HusqvarnaCoordinator entity for Husqvarna Automower Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HusqvarnaCoordinator) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.address}_{coordinator.channel_id}")},
            manufacturer=MANUFACTURER,
            model=coordinator.model,
        )

        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.mower.is_connected()
