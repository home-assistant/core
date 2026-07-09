"""Base entities for the Subaru integration."""

from typing import Any, override

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_info
from .const import VEHICLE_VIN
from .coordinator import SubaruDataUpdateCoordinator


class SubaruEntity(Entity):
    """Base class for Subaru entities.

    Owns device_info, unique_id, and the has_entity_name convention so
    every Subaru entity has the same shape without each platform repeating
    the boilerplate. Used directly by entities that do not back onto a
    DataUpdateCoordinator (button, lock); coordinator-backed entities
    use SubaruCoordinatorEntity instead.
    """

    _attr_has_entity_name = True

    def __init__(self, vehicle_info: dict[str, Any], unique_id_suffix: str) -> None:
        """Initialize the entity from the vehicle_info dict."""
        self.vehicle_info = vehicle_info
        self.vin: str = vehicle_info[VEHICLE_VIN]
        self._attr_device_info = get_device_info(vehicle_info)
        self._attr_unique_id = f"{self.vin}_{unique_id_suffix}"


class SubaruCoordinatorEntity(
    CoordinatorEntity[SubaruDataUpdateCoordinator], SubaruEntity
):
    """Base class for coordinator-backed Subaru entities.

    Subclasses CoordinatorEntity for the polling lifecycle and the
    `last_update_success` availability gate, and composes the device_info /
    unique_id handling from SubaruEntity. Override `available` here so the
    entity is unavailable when the coordinator has not reported data for
    this specific vehicle, even if its overall fetch succeeded.
    """

    def __init__(
        self,
        vehicle_info: dict[str, Any],
        coordinator: SubaruDataUpdateCoordinator,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the coordinator-backed entity."""
        super().__init__(coordinator)
        SubaruEntity.__init__(self, vehicle_info, unique_id_suffix)

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.vin in self.coordinator.data
