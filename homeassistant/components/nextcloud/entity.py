"""Base entity for the Nextcloud integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator


class NextcloudEntity(CoordinatorEntity[NextcloudDataUpdateCoordinator]):
    """Base Nextcloud entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud"

    def __init__(
        self, coordinator: NextcloudDataUpdateCoordinator, item: str, entry: ConfigEntry
    ) -> None:
        """Initialize the Nextcloud sensor."""
        super().__init__(coordinator)
        self.item = item
        self._attr_translation_key = slugify(item)
        self._attr_unique_id = f"{coordinator.url}#{item}"
        self._attr_device_info = DeviceInfo(
            name="Nextcloud",
            identifiers={(DOMAIN, entry.entry_id)},
            sw_version=coordinator.data.get("nextcloud_system_version"),
            configuration_url=coordinator.url,
        )
