"""The Deluge integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import DelugeDataUpdateCoordinator


class DelugeEntity(CoordinatorEntity[DelugeDataUpdateCoordinator]):
    """Representation of a Deluge entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DelugeDataUpdateCoordinator) -> None:
        """Initialize a Deluge entity."""
        super().__init__(coordinator)
        self._server_unique_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            configuration_url=(
                f"http://{coordinator.api.host}:{coordinator.api.web_port}"
            ),
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            sw_version=coordinator.api.deluge_version,
        )
