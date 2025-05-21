"""Paperless-ngx base entity."""

from __future__ import annotations

from homeassistant.components.sensor import EntityDescription
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PaperlessConfigEntry, PaperlessCoordinator


class PaperlessEntity(CoordinatorEntity[PaperlessCoordinator]):
    """Defines a base Paperless-ngx entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PaperlessConfigEntry,
        coordinator: PaperlessCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Paperless-ngx entity."""
        CoordinatorEntity.__init__(
            self,
            coordinator=coordinator,
        )

        self.entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.entry.entry_id)},
            manufacturer="Paperless-ngx",
            name=coordinator.api.base_url,
            sw_version=self.entry.runtime_data.api.host_version,
            configuration_url=self.entry.runtime_data.api.base_url,
        )
