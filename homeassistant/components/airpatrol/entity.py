"""Base entity for AirPatrol integration."""

from __future__ import annotations

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
        unit: dict,
        unit_id: str,
    ) -> None:
        """Initialize the AirPatrol entity."""
        super().__init__(coordinator)
        self._unit = unit
        self._unit_id = unit_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit_id)},
            name=unit.get("name", f"AirPatrol {unit_id}"),
            manufacturer=unit.get("manufacturer", "AirPatrol"),
            model=unit.get("model"),
            sw_version=unit.get("sw_version"),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and any(
            unit.get("unit_id") == self._unit_id for unit in self.coordinator.data
        )
