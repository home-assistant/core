"""Base entity for WAFE heat recovery units."""

from typing import TYPE_CHECKING

from wafe_modbus import WafeUnit

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WafeDataUpdateCoordinator


class WafeEntity(CoordinatorEntity[WafeDataUpdateCoordinator]):
    """An entity of a WAFE unit."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WafeDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id is not None
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        self._attr_device_info = coordinator.device_info

    @property
    def device(self) -> WafeUnit:
        """The library object of the unit."""
        return self.coordinator.device
