"""Base entity for the Nextcloud integration."""

from urllib.parse import urlparse

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NextcloudConfigEntry
from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator


class NextcloudEntity(CoordinatorEntity[NextcloudDataUpdateCoordinator]):
    """Base Nextcloud entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextcloudDataUpdateCoordinator,
        entry: NextcloudConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize the Nextcloud sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}#{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.url,
            identifiers={(DOMAIN, entry.entry_id)},
            name=urlparse(coordinator.url).netloc,
            sw_version=coordinator.data.get("system_version"),
        )
        self.entity_description = description
