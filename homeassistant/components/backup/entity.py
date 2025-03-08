"""Base for backup entities."""

from __future__ import annotations

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BackupDataUpdateCoordinator


class BackupManagerEntity(CoordinatorEntity[BackupDataUpdateCoordinator]):
    """Base entity for backup manager."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BackupDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = entity_description.key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "backup_manager")},
            manufacturer="Home Assistant",
            model="Home Assistant Backup",
            sw_version=HA_VERSION,
            name="Backup",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="homeassistant://config/backup",
        )
