"""Paperless-ngx base entity."""

from __future__ import annotations

from homeassistant.components.sensor import EntityDescription
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PaperlessCoordinator


class PaperlessEntity[CoordinatorT: PaperlessCoordinator](
    CoordinatorEntity[CoordinatorT]
):
    """Defines a base Paperless-ngx entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoordinatorT,
        description: EntityDescription,
    ) -> None:
        """Initialize the Paperless-ngx entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Paperless-ngx",
            sw_version=coordinator.api.host_version,
            configuration_url=coordinator.api.base_url,
        )
