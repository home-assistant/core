"""Base entity for Idasen Desk."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IdasenDeskCoordinator


class IdasenDeskEntity(CoordinatorEntity[IdasenDeskCoordinator]):
    """IdasenDesk sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        coordinator: IdasenDeskCoordinator,
    ) -> None:
        """Initialize the IdasenDesk sensor entity."""
        super().__init__(coordinator)

        self._attr_unique_id = unique_id
        self._attr_device_info = dr.DeviceInfo(
            manufacturer="LINAK",
            connections={(dr.CONNECTION_BLUETOOTH, coordinator.address)},
        )
        self._desk = coordinator.desk

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._desk.is_connected is True
