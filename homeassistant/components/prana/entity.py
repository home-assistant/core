"""Defines base Prana entity."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PranaCoordinator


class PranaBaseEntity(CoordinatorEntity[PranaCoordinator]):
    """Defines a base Prana entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PranaCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Prana entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            manufacturer="Prana",
            name=coordinator.device_info.label,
            model=coordinator.device_info.pranaModel,
            serial_number=coordinator.device_info.manufactureId,
            sw_version=str(coordinator.device_info.fwVersion),
        )
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self.entity_description = description
