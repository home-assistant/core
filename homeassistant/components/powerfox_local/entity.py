"""Base entity for Powerfox Local."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PowerfoxLocalDataUpdateCoordinator


class PowerfoxLocalEntity(CoordinatorEntity[PowerfoxLocalDataUpdateCoordinator]):
    """Base entity for Powerfox Local."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PowerfoxLocalDataUpdateCoordinator,
    ) -> None:
        """Initialize Powerfox Local entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Powerfox",
            model="Poweropti",
            serial_number=coordinator.device_id,
        )
