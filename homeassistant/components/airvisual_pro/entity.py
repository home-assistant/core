"""The AirVisual Pro integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class AirVisualProEntity(CoordinatorEntity):
    """Define a generic AirVisual Pro entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.data['serial_number']}_{description.key}"
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data["serial_number"])},
            manufacturer="AirVisual",
            model=self.coordinator.data["status"]["model"],
            name=self.coordinator.data["settings"]["node_name"],
            hw_version=self.coordinator.data["status"]["system_version"],
            sw_version=self.coordinator.data["status"]["app_version"],
        )
