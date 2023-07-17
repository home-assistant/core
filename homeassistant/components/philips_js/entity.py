"""Base Philips js entity."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN


class PhilipsJsEntity(CoordinatorEntity[PhilipsTVDataUpdateCoordinator]):
    """Base Philips js entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize light."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            },
            manufacturer="Philips",
            model=coordinator.system.get("model"),
            name=coordinator.system["name"],
            sw_version=coordinator.system.get("softwareversion"),
        )
