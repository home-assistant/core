"""Base entity for the Möhlenhoff Alpha2 integration."""

from typing import Any, override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Alpha2BaseCoordinator


class Alpha2RoomEntity(CoordinatorEntity[Alpha2BaseCoordinator]):
    """Base class for entities associated with a heat area."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Alpha2BaseCoordinator, heat_area_id: str) -> None:
        """Initialize the room entity."""
        super().__init__(coordinator)
        self.heat_area_id = heat_area_id

    @property
    def heat_area(self) -> dict[str, Any]:
        """Return the heat area."""
        return self.coordinator.data["heat_areas"][self.heat_area_id]

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.heat_area_id)},
            manufacturer="Möhlenhoff",
            model="Alpha2",
            name=self.heat_area["HEATAREA_NAME"],
        )
