"""Base entity for the RDW integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RDWDataUpdateCoordinator


class RDWEntity(CoordinatorEntity[RDWDataUpdateCoordinator]):
    """Defines an RDW entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RDWDataUpdateCoordinator) -> None:
        """Initialize an RDW entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.data.license_plate)},
            manufacturer=coordinator.data.brand,
            name=f"{coordinator.data.brand} {coordinator.data.license_plate}",
            model=coordinator.data.model,
            configuration_url=f"https://ovi.rdw.nl/default.aspx?kenteken={coordinator.data.license_plate}",
        )
