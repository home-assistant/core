"""Base entity for Idasen Desk."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DeskData, IdasenDeskCoordinator


class IdasenDeskEntity(CoordinatorEntity[IdasenDeskCoordinator]):
    """IdasenDesk sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        desk_data: DeskData,
    ) -> None:
        """Initialize the IdasenDesk sensor entity."""
        super().__init__(desk_data.coordinator)

        self._attr_unique_id = unique_id
        self._attr_device_info = dr.DeviceInfo(
            name=desk_data.device_name,
            connections={(dr.CONNECTION_BLUETOOTH, desk_data.address)},
        )
        self._desk = desk_data.coordinator.desk

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._desk.is_connected is True
