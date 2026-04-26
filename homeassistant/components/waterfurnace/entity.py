"""Base entity for WaterFurnace."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WaterFurnaceCoordinator


class WaterFurnaceEntity(CoordinatorEntity[WaterFurnaceCoordinator]):
    """Base entity for WaterFurnace."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WaterFurnaceCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unit)},
            manufacturer="WaterFurnace",
            name="WaterFurnace System",
        )

        if coordinator.device_metadata:
            if coordinator.device_metadata.description:
                device_info["model"] = coordinator.device_metadata.description
            if coordinator.device_metadata.awlabctypedesc:
                device_info["name"] = coordinator.device_metadata.awlabctypedesc

        self._attr_device_info = device_info
