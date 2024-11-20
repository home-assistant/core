"""Base entity for pyLoad."""

from __future__ import annotations

from homeassistant.components.button import EntityDescription
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SERVICE_NAME
from .coordinator import PyLoadCoordinator


class BasePyLoadEntity(CoordinatorEntity[PyLoadCoordinator]):
    """BaseEntity for pyLoad."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the Entity."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=SERVICE_NAME,
            configuration_url=coordinator.pyload.api_url,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            sw_version=coordinator.version,
        )
