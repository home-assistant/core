"""Base entity for AirPatrol integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirPatrolDataUpdateCoordinator


class AirPatrolEntity(CoordinatorEntity[AirPatrolDataUpdateCoordinator]):
    """Base entity for AirPatrol devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirPatrolDataUpdateCoordinator,
        unit_id: str,
    ) -> None:
        """Initialize the AirPatrol entity."""
        super().__init__(coordinator)
        self._unit_id = unit_id
        device = coordinator.data[unit_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit_id)},
            name=device["name"],
            manufacturer=device["manufacturer"],
            model=device["model"],
            serial_number=device["hwid"],
        )

    @property
    def device_data(self) -> dict[str, Any]:
        """Return the device data."""
        return self.coordinator.data[self._unit_id]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and bool(self.device_data)
