"""Support for UV data from openuv.io."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenUvCoordinator


class OpenUvEntity(CoordinatorEntity):
    """Define a generic OpenUV entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OpenUvCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = (
            f"{coordinator.latitude}_{coordinator.longitude}_{description.key}"
        )
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.latitude}_{coordinator.longitude}")},
            name="OpenUV",
            entry_type=DeviceEntryType.SERVICE,
        )
